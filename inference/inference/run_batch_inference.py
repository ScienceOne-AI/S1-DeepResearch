import argparse
import asyncio
import datetime
import json
import os
import sys
import time

from anyio import Path
from numpy._core.numerictypes import str_


# 获取项目根目录路径，并加入 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from inference.run_single_inference import run_one_query
from server.llm_api import LLMClient
from server.tool_api import return_all_tools
from utils.configs import LITERATURE_SEED_DATA_DIR

from tqdm import tqdm  # pyright: ignore[reportMissingModuleSource]
from typing import Any, Dict
from utils.common import _to_bool, get_query_uuid, load_jsonl
from utils.logger import setup_collect_logger
from utils.prompts import DEEPRESEARCH_SYSTEM_PROMPT
from utils.skill_prompt import build_skills_system_text, extract_skills_from_row, resolve_skill_source_dirs
from utils.build_prompt import build_openai_schema

def parse_args():
    parser = argparse.ArgumentParser(description="批量推理脚本")
    parser.add_argument("--llm_client_urls", type=str, nargs='+', default=["http://10.20.4.18:10777/vllm_generate"], help="vllm 远程挂载的模型 URL (可传多个，用空格分隔)")
    parser.add_argument("--llm_client_models", type=str, nargs='+', default=["LLM_CLIENT_NAME"], help="vllm 远程挂载的模型名称 (可传多个，用空格分隔)")
    parser.add_argument("--test_data_file", type=str, default="test_files/test.jsonl", help="测试需要生成答案的文件(.jsonl)")
    parser.add_argument("--available_tools", type=str, nargs="+", default=["web_search", "visit_url", "execute_code"], help="可用的tool名称（列表）")
    parser.add_argument("--resume_from_file", type=str, default="test_files/test_result_20251112.jsonl", help="已完成结果的本地文件(可选)，自动跳过已完成样本")
    parser.add_argument("--concurrency_workers", type=int, default=10, help="并发进程数量")
    parser.add_argument("--save_batch_size", type=int, default=1, help="每得到多少条数据结果就存储一次")
    parser.add_argument("--rollout_num", type=int, default=1, help="每条数据的推理次数，每次推理结果以rollout_xx.jsonl命名保存到output_dir中")
    parser.add_argument("--max_rounds", type=int, default=100, help="与模型交互的最大轮数")
    parser.add_argument("--temperature", type=float, default=0.7, help="采样温度")
    parser.add_argument("--top_p", type=float, default=0.95, help="nucleus sampling 的 top_p 参数")
    parser.add_argument("--extra_payload", type=str, default="{}", help="额外的 payload 参数（JSON 字符串），如 '{\"presence_penalty\": 1.1}'")
    parser.add_argument("--timeout_for_one_query", type=int, default=7200, help="单个query最大执行时长（秒）")
    parser.add_argument("--llm_api_retry_times", type=int, default=2, help="LLM API 请求失败后的重试次数，不含首次请求")
    parser.add_argument("--output_file", type=str, default="test_files/test_result_today.jsonl", help="结果输出文件路径")
    parser.add_argument("--output_dir", type=str, default="test_files/output", help="结果输出目录路径（每个rollout结果以rollout_xx.jsonl保存）")
    parser.add_argument('--system_format', type=str, default="deep_research", help="采用什么模型的prompt拼接方式(默认用 deep_research 的)")
    parser.add_argument('--log_label', type=str, default="", help=f"log 路径加入自定义文本标记，同时也是附件类数据暂存附件的存储路径 {LITERATURE_SEED_DATA_DIR}/{{log_label}}")
    parser.add_argument('--system_prompt', type=str, default=None, help="自定义全局system_prompt的文件路径或字符串(默认用DEEPRESEARCH)")
    parser.add_argument('--verbose', action='store_true', default=True, help="是否输出debug日志")
    parser.add_argument('--clean_files_copy_dir', action='store_true', default=False, help="执行完后是否删除files_copy_dir临时文件夹")
    parser.add_argument("--discard_all_mode", type=str, default="false", help="是否开启 discard-all 模式（true/false）")
    parser.add_argument("--model_max_context_tokens", type=int, default=128000, help="模型最大上下文长度")
    parser.add_argument("--discard_ratio", type=float, default=0.8, help="触发 discard 的上下文比例阈值")
    parser.add_argument("--tokenizer_path", type=str, default="models/tokenizer", help="用于 token 统计的 tokenizer 路径")
    parser.add_argument("--logging_root", type=str, default=None, help="用于自定义 log 存储路径")
    return parser.parse_args()

# 工具注册 全局，减少取用延迟
ALL_TOOLS = return_all_tools()

async def main_async(args):
    # --- 日志
    logging_root = args.logging_root if args.logging_root else project_root
    logger, log_path = setup_collect_logger(logging_root, args.log_label)
    logger.info(f"[Collector] Script Start. Log file: {log_path}")

    # --------- 参数处理与初始化 ---------
    def abs_path_if_needed(path):
        if not path:
            return path
        # 如果是相对路径，且不是以.或..开头，拼接到project_root；否则用os.path.abspath
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
    top_p = args.top_p
    _extra_raw = (args.extra_payload or "").strip()
    extra_payload = json.loads(_extra_raw if _extra_raw else "{}")
    system_format = args.system_format
    timeout_for_one_query = args.timeout_for_one_query
    llm_api_retry_times = max(0, args.llm_api_retry_times)
    output_file = abs_path_if_needed(args.output_file)
    output_dir = abs_path_if_needed(args.output_dir)
    rollout_num = args.rollout_num
    discard_all_mode = _to_bool(args.discard_all_mode)
    model_max_context_tokens = args.model_max_context_tokens
    discard_ratio = args.discard_ratio
    tokenizer_path = abs_path_if_needed(args.tokenizer_path)
    # 检查并创建 output_file 的文件夹（如果不存在）
    output_dir_from_file = os.path.dirname(output_file)
    if output_dir_from_file and not os.path.exists(output_dir_from_file):
        logger.warning(f"[Save Dir created] Make the dir {output_dir_from_file}")
        os.makedirs(output_dir_from_file, exist_ok=True)
    if output_dir and not os.path.exists(output_dir):
        logger.warning(f"[Save Dir created] Make the dir {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
    verbose = args.verbose
    # system prompt来源：命令行 > 默认常量
    if args.system_prompt:
        if os.path.isfile(args.system_prompt):
            with open(args.system_prompt, encoding="utf-8") as f:
                system_prompt = f.read()
        else:
            system_prompt = args.system_prompt
    else:
        system_prompt = DEEPRESEARCH_SYSTEM_PROMPT

    # 剔除未启用的工具
    selected_tools = {name: spec for name, spec in ALL_TOOLS.items() if name in available_tools}

    logger.info(f"[Selected_tools] {build_openai_schema(selected_tools)}")

    llm_client = LLMClient(
        llm_client_urls,
        llm_client_models,
        max_retries=llm_api_retry_times,
    )
    data_list = load_jsonl(test_data_file)  # 加载全部待推理数据

    logger.info(f"Number of rollouts per query: {rollout_num}")
    logger.info(f"LLM API retry times: {llm_api_retry_times}")

    # 为每个rollout准备输出文件路径
    rollout_output_files = {}
    if rollout_num > 1:
        for rollout_idx in range(1, rollout_num + 1):
            rollout_output_file = os.path.join(output_dir, f"rollout_{rollout_idx:02d}.jsonl")
            rollout_output_files[rollout_idx] = rollout_output_file
            logger.info(f"Rollout {rollout_idx}: output_file={rollout_output_file}")
    else:
        rollout_output_files[1] = output_file

    # 记录本轮中有用到文件拷贝的目录，最后用来删除
    files_copy_dir = None
    if args.log_label:
        files_copy_dir = f"data/{args.log_label}"

    # 处理每个rollout
    for rollout_idx in range(1, rollout_num + 1):
        logger.info(f"{'='*50}")
        logger.info(f"Starting Rollout {rollout_idx}/{rollout_num}")
        logger.info(f"{'='*50}")

        rollout_output_file = rollout_output_files.get(rollout_idx, output_file)

        results = []
        finished_keys = set()

        def _get_finish_key_from_item(item: Dict[str, Any]) -> str:
            """
            用于判定一条 query 是否已完成的 key。
            - 修改 key 的逻辑，将 id + query 的内容同时作为 id 进行判定，这样能够避免某些数据集 id 没有处理干净的情况
            """
            if not isinstance(item, dict):
                return ""
            now_id = ""
            _id = item.get("id", None)
            if _id is not None and str(_id) != "":
                now_id += str(_id)
            q = item.get("question", None)
            if q is not None and str(q) != "":
                now_id += "__" + str(q)
            return now_id

        # --------- 恢复完成数据 ---------
        # 优先用 args.resume_from_file，其次用当前rollout的output_file
        resume_path = None
        if resume_from_file and os.path.isfile(resume_from_file):
            resume_path = resume_from_file
        elif os.path.isfile(rollout_output_file):
            resume_path = rollout_output_file

        if resume_path:
            logger.info(f"[Resume Rollout {rollout_idx}] Loading finished IDs from: {resume_path}")
            with open(resume_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        src = obj.get("src") or {}
                        # 兼容旧输出：src 里可能没有 id；同时回退到 obj.query
                        key = _get_finish_key_from_item(src)
                        if not key:
                            q = obj.get("query", None)
                            key = "" if q is None else str(q)
                        # if key and obj.get("status", "") == "success":
                        if key and obj.get("status", "") == "success" and obj.get("result", {}).get("final_answer"):
                            # 正确且 success 的留下
                            finished_keys.add(key)
                            results.append(obj)
                    except Exception:
                        continue
        # 只保留未完成的条目
        original_num = len(data_list)
        data_list_for_rollout = [item for item in data_list if _get_finish_key_from_item(item) not in finished_keys]
        logger.info(f"[Resume Rollout {rollout_idx}] Skipped {len(finished_keys)} finished items, {len(data_list_for_rollout)} remaining (total={original_num}).")

        if not data_list_for_rollout:
            logger.info(f"[Rollout {rollout_idx}] All queries already processed, skipping.")
            continue

        # --------- 并发控制 ---------
        sem = asyncio.Semaphore(concurrency_workers)
        save_every = save_batch_size

        async def _worker(idx: int, item: Dict[str, Any], rollout_idx: int):
            async with sem:
                query = item.get("question")
                id = item.get("id")
                query_id = get_query_uuid(str(query))
                file_path = item.get("file_path", "")

                # 统一将 file_path 转为 list 处理（兼容 str 和 list 和 None）
                file_paths = []
                if isinstance(file_path, list):
                    file_paths = file_path
                elif isinstance(file_path, str) and file_path:
                    file_paths = [file_path]

                start = time.time()
                progress = {}
                # 抽取行中的 skill 字段信息
                row_skills = extract_skills_from_row(item)
                # 拼接成 # Skill 部分的文本内容
                system_skill_text = build_skills_system_text(row_skills) if row_skills else None
                # 记录所有的 skill 的绝对路径
                skill_source_dirs = resolve_skill_source_dirs(row_skills, project_root) if row_skills else []
                try:
                    result = await asyncio.wait_for(
                        run_one_query(
                            llm=llm_client, 
                            user_query=str(query), 
                            file_path=file_paths, # 将真实的 file_paths 传入，在内部进行图像的拷贝
                            system=system_prompt,
                            max_rounds=max_rounds, 
                            temperature=temperature,
                            top_p=top_p,
                            extra_payload=extra_payload,
                            debug=verbose,
                            progress=progress,
                            all_tools=selected_tools,
                            system_format = system_format,
                            log_label = args.log_label,
                            file_prefix = "", # 由内部进行设定，因为现在还不知道 query_id (也就是工具需要的 conversation_id) 是多少
                            discard_all_mode=discard_all_mode,
                            model_max_context_tokens=model_max_context_tokens,
                            discard_ratio=discard_ratio,
                            tokenizer_path=tokenizer_path,
                            logging_root=logging_root,
                            skill_source_dirs=skill_source_dirs,
                            system_skill_text=system_skill_text,
                        ),
                        timeout=timeout_for_one_query
                    )
                    status = "success"
                except asyncio.TimeoutError:
                    status = "timeout"
                    result = progress.get('result', [])
                    logger.error(f"[Timeout] id={id}, query_id={query_id}, elapsed={round(time.time() - start, 3)}s")
                except Exception as e:
                    status = "error"
                    result = progress.get('result', [])
                    if isinstance(result, list):
                        if not result:
                            result = [{"error": str(e)}]
                        else:
                            result[-1]["error"] = str(e)
                    logger.error(f"[Error] id={id}, query_id={query_id}, err={e}")
                elapsed = time.time() - start
                llm_client.pop_query_id(query_id) # llm_client 弹出当前 query 用于动态记录负载
                logger.info(f"[Finish] id={id}, query_id={query_id}, status={status}, elapsed={round(elapsed,3)}s")
                discard_segments = sum(
                    1
                    for rr in (result or [])
                    if isinstance(rr, dict) and str(rr.get("stopped_reason", "")).startswith("discard_all_")
                    and rr.get("stopped_reason") != "discard_all_final"
                )
                return {
                    "time_stamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "query_id": query_id,
                    "query": query,
                    "result": result,
                    "status": status,
                    "discard_segments": discard_segments, # 统计当前有多少个 summary 碎片（即没有 <answer>..</answer>, 而是被强行截断的）
                    "elapsed_sec": round(elapsed, 3),
                    "rollout_idx": rollout_idx,
                    "src": item,
                }

        # --------- 分派任务 & tqdm进度 ---------
        tasks = [asyncio.create_task(_worker(i, item, rollout_idx)) for i, item in enumerate(data_list_for_rollout)]
        pbar = tqdm(total=len(tasks), desc=f"Rollout {rollout_idx}/{rollout_num}", ncols=80)
        finished = 0

        # --------- result循环处理&定期保存 ---------
        for coro in asyncio.as_completed(tasks):
            r = await coro
            seg_results = r.get("result", [])
            if isinstance(seg_results, dict):
                seg_results = [seg_results]
            if not isinstance(seg_results, list):
                seg_results = []

            if not seg_results:
                row = dict(r)
                row["result"] = {}
                row["segment_idx"] = 1
                row["segment_total"] = 0
                results.append(row)
            else:
                total = len(seg_results)
                for seg_idx, seg in enumerate(seg_results, start=1):
                    row = dict(r)
                    row["result"] = seg
                    row["segment_idx"] = seg_idx # 下标从 1 开始
                    row["segment_total"] = total # 一共有几个片段（最后的有 <answer> 的也算一个片段）
                    results.append(row)

            finished += 1
            pbar.update(1)
            # 定期保存
            if rollout_output_file and save_every and finished % save_every == 0:
                with open(rollout_output_file, "w", encoding="utf-8") as f:
                    for rr in results:
                        f.write(json.dumps(rr, ensure_ascii=False) + "\n")
                logger.info(f"[AutoSave Rollout {rollout_idx}] Progress saved to: {rollout_output_file} ({finished}/{len(tasks)})")
        pbar.close()

        # --------- 最后一次保存 ---------
        if rollout_output_file:
            with open(rollout_output_file, "w", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            logger.info(f"[Rollout {rollout_idx}] Wrote results to: {rollout_output_file}")

    logger.info(f"{'='*50}")
    logger.info(f"All {rollout_num} rollouts completed!")
    logger.info(f"{'='*50}")
    logger.info("[Collector] Script finished.")

    # ===== Final clean-up: 删除文件拷贝过去的目录 =====
    if args.clean_files_copy_dir:  # 只有开启该参数才清理
        if files_copy_dir and os.path.exists(files_copy_dir):
            try:
                import shutil
                shutil.rmtree(files_copy_dir)
                logger.info(f"[Cleanup] Removed copied files directory: {files_copy_dir}")
            except Exception as e:
                logger.error(f"[Cleanup] Failed to remove directory {files_copy_dir}: {e}")


def main():
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("Interrupted by user.")

if __name__ == "__main__":
    main()