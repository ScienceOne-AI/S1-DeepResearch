import argparse
import asyncio
import datetime
import json
import os
import sys
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from inference.run_single_inference import run_one_query
from server.llm_api import LLMClient
from server.tool_api import return_all_tools

from tqdm import tqdm
from typing import Any, Dict
from utils.common import get_query_uuid, load_jsonl
from utils.logger import setup_collect_logger
from utils.prompts import TONGYI_DEEPRESEARCH_SYSTEM_PROMPT
from utils.build_prompt import build_openai_schema

def parse_args():
    parser = argparse.ArgumentParser(description="Batch inference script")
    parser.add_argument("--llm_client_urls", type=str, nargs='+', default=["http://10.20.4.18:10777/vllm_generate"], help="Remote model URL(s) mounted to vllm (multiple allowed, space separated)")
    parser.add_argument("--llm_client_models", type=str, nargs='+', default=["<model_name>"], help="Model name(s) for vllm remote mount (multiple allowed, space separated)")
    parser.add_argument("--test_data_file", type=str, default="test_files/test.jsonl", help="Test file containing input data (.jsonl) for answer generation")
    parser.add_argument("--available_tools", type=str, nargs="+", default=["web_search", "visit_url", "execute_code"], help="Available tool names (list)")
    parser.add_argument("--resume_from_file", type=str, default="test_files/test_result_20251112.jsonl", help="File containing already completed results (optional), will skip completed samples automatically")
    parser.add_argument("--concurrency_workers", type=int, default=10, help="Number of concurrent workers")
    parser.add_argument("--save_batch_size", type=int, default=1, help="Number of results after which to save output")
    parser.add_argument("--max_rounds", type=int, default=100, help="Maximum number of model interaction rounds")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    parser.add_argument("--timeout_for_one_query", type=int, default=7200, help="Max execution time (seconds) for a single query")
    parser.add_argument("--output_file", type=str, default="test_files/test_result_today.jsonl", help="Output file path for results")
    parser.add_argument('--system_format', type=str, default=None, help="Prompt composition format for which model")
    parser.add_argument('--log_label', type=str, default="", help="Custom text label for log path")
    parser.add_argument('--system_prompt', type=str, default=None, help="Path or string for custom global system prompt")
    parser.add_argument('--verbose', action='store_true', default=True, help="Whether to output debug logs")
    return parser.parse_args()

ALL_TOOLS = return_all_tools()

async def main_async(args):
    logger, log_path = setup_collect_logger(project_root, args.log_label)
    logger.info(f"[Collector] Script Start. Log file: {log_path}")

    # --------- Parameter processing and initialization ---------
    def abs_path_if_needed(path):
        if not path:
            return path
        if not os.path.isabs(path):
            if path.startswith("./") or path.startswith("../"):
                return os.path.abspath(path)
            else:
                return os.path.join(project_root, path)
        return path

    llm_client_urls = args.llm_client_urls
    llm_client_models = args.llm_client_models
    test_data_file = abs_path_if_needed(args.test_data_file)
    available_tools = args.available_tools
    resume_from_file = abs_path_if_needed(args.resume_from_file)
    concurrency_workers = args.concurrency_workers
    save_batch_size = args.save_batch_size
    max_rounds = args.max_rounds
    temperature = args.temperature
    system_format = args.system_format
    timeout_for_one_query = args.timeout_for_one_query
    output_file = abs_path_if_needed(args.output_file)
    # Check and create output_file's directory (if it doesn't exist)
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        logger.warning(f"[Save Dir created] Make the dir {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
    verbose = args.verbose
    # system prompt source: command line > default constant
    if args.system_prompt:
        if os.path.isfile(args.system_prompt):
            with open(args.system_prompt, encoding="utf-8") as f:
                system_prompt = f.read()
        else:
            system_prompt = args.system_prompt
    else:
        system_prompt = TONGYI_DEEPRESEARCH_SYSTEM_PROMPT

    # Remove unavailable tools
    selected_tools = {name: spec for name, spec in ALL_TOOLS.items() if name in available_tools}

    logger.info(f"[Selected_tools] {build_openai_schema(selected_tools)}")

    llm_client = LLMClient(llm_client_urls, llm_client_models)
    data_list = load_jsonl(test_data_file)  # Load all samples for inference

    results = []
    finished_ids = set()

    # --------- Resume finished data ---------
    if resume_from_file and os.path.isfile(resume_from_file):
        logger.info(f"[Resume] Loading finished IDs from: {resume_from_file}")
        with open(resume_from_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    finished_ids.add(obj.get("src").get("id"))
                    results.append(obj)
                except Exception:
                    continue
    # Only keep unfinished entries
    original_num = len(data_list)
    data_list = [item for item in data_list if item.get("id", "") not in finished_ids]
    logger.info(f"[Resume] Skipped {len(finished_ids)} finished items, {len(data_list)} remaining (total={original_num}).")

    # --------- Concurrency control ---------
    sem = asyncio.Semaphore(concurrency_workers)
    save_every = save_batch_size

    async def _worker(idx: int, item: Dict[str, Any]):
        async with sem:
            query = item.get("question")
            id = item.get("id")
            query_id = get_query_uuid(query)
            file_path = item.get("file_path", "")
            # File existence check
            if file_path:
                if os.path.isfile(file_path):
                    logger.info(f"[File load] Get file `{file_path}` for id={id}, query_id={query_id}")
                else:
                    logger.warning(f"File not found for id={id}, query_id={query_id}: expected {file_path}")
                
            start = time.time()
            progress = {}
            try:
                result = await asyncio.wait_for(
                    run_one_query(
                        llm=llm_client, 
                        user_query=query, 
                        file_path=file_path, 
                        system=system_prompt,
                        max_rounds=max_rounds, 
                        temperature=temperature, 
                        debug=verbose,
                        progress=progress,
                        all_tools=selected_tools,
                        system_format = system_format,
                        log_label = args.log_label,
                    ),
                    timeout=timeout_for_one_query
                )
                status = "success"
            except asyncio.TimeoutError:
                status = "timeout"
                result = progress.get('result', {})
                logger.error(f"[Timeout] id={id}, query_id={query_id}, elapsed={round(time.time() - start, 3)}s")
            except Exception as e:
                status = "error"
                result = progress.get('result', {})
                result['error'] = str(e)
                logger.error(f"[Error] id={id}, query_id={query_id}, err={e}")
            elapsed = time.time() - start
            llm_client.pop_query_id(query_id) # llm_client pops current query to dynamically track load
            logger.info(f"[Finish] id={id}, query_id={query_id}, status={status}, elapsed={round(elapsed,3)}s")
            return {
                "time_stamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "query_id": query_id,
                "query": query,
                "result": result,
                "status": status,
                "elapsed_sec": round(elapsed, 3),
                "src": item,
            }

    # --------- Dispatch tasks & tqdm progress ---------
    tasks = [asyncio.create_task(_worker(i, item)) for i, item in enumerate(data_list)]
    pbar = tqdm(total=len(tasks), desc="Processing", ncols=80)
    finished = 0

    # --------- Process results & save periodically ---------
    for coro in asyncio.as_completed(tasks):
        r = await coro
        results.append(r)
        finished += 1
        pbar.update(1)
        # Save periodically
        if output_file and save_every and finished % save_every == 0:
            with open(output_file, "w", encoding="utf-8") as f:
                for rr in results:
                    f.write(json.dumps(rr, ensure_ascii=False) + "\n")
            logger.info(f"[AutoSave] Progress saved to: {output_file} ({finished}/{len(tasks)})")
    pbar.close()

    # --------- Final save ---------
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logger.info(f"[FinalSave] Wrote results to: {output_file}")
    logger.info("[Collector] Script finished.")

def main():
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("Interrupted by user.")

if __name__ == "__main__":
    main()

    # Example nohup start command (CLI)
    # -------------------------------------------
    # nohup python inference/run_batch_inference.py \
    #   --llm_client_urls "http://127.0.0.1:10777/vllm_generate" "http://127.0.0.1:10888/vllm_generate"\ 
    #   --test_data_file="./test_files/test.jsonl" \
    #   --output_file="./test_files/test_result_today.jsonl" \
    #   --available_tools web_search visit_url execute_code \
    #   --concurrency_workers 8 \
    #   --save_batch_size 10 \
    #   --max_rounds 50 \
    #   --temperature 0.85 \
    #   --timeout_for_one_query 1800 \
    #   --resume_from_file="./test_files/test_result_today.jsonl" \
    #   --system_prompt="./sys_prompt.txt" \
    #   --verbose > run_batch.log 2>&1 &
    
    # tail -f run_batch.log
    # -------------------------------------------