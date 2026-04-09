# 配置入口说明

## 1. 整体说明

目前所有的配置项统一成了一套明确的三层配置系统，并保留了原来的 `utils.configs` 使用入口，尽量不影响现有业务代码。

特性：

- 支持统一从自定义 JSON、环境变量、`utils/config.py` 读取配置。
- 尽量兼容现有代码中 `from utils.configs import XXX` 的写法。
- 降低后续新增、删除、排查配置项时的维护成本。

当前配置优先级如下：

1. 自定义 JSON 文件
2. 环境变量
3. `utils/config.py` 中的默认值

也就是说：**越靠前优先级越高**。

---

## 2. 配置相关文件总览

本次改动后，配置系统的核心文件如下：

- `utils/config.py`
  - 默认配置定义文件。
  - 新增配置项时，首先应该在这里定义默认值。
- `utils/config_loader.py`
  - 配置加载核心逻辑。
  - 负责自动发现配置项、按优先级加载、做环境变量类型转换。
- `utils/configs.py`
  - 对外兼容层。
  - 旧代码仍然可以继续 `from utils.configs import XXX`。
- `utils/config/config.example.json`
  - JSON 配置样例。
- `utils/config/README.md`
  - 即当前文档，说明原理、使用方式和维护规范。

---

## 3. 整体工作流程

程序启动后，如果某处代码执行了：

```python
from utils.configs import CLIENT_TIMEOUT
```

或者：

```python
import utils.configs as configs
```

会触发如下链路：

1. Python 加载 `utils/configs.py`
2. `utils/configs.py` 再导入 `utils/config_loader.py`
3. `utils/config_loader.py` 在模块导入阶段创建 `_CONFIG_MANAGER = ConfigManager()`
4. `ConfigManager()` 内部加载 `utils.config`
5. 自动扫描 `utils.config` 中所有符合条件的“大写配置项”
6. 建立三层配置源：JSON、环境变量、默认 `config.py`
7. `utils.configs` 再把最终配置值暴露给业务代码

因此：

- **只要业务代码 import 了 `utils.configs`，这套配置逻辑就会启动**。
- **从使用视角看，只要在 `utils.configs` 可访问到一个新增的全大写配置变量，就可以直接通过 JSON / 环境变量配置后启动评测；按当前实现，这个变量的定义应新增在 `utils/config.py`，详细维护方式见后文的[开发者维护指南](#developer-guide)和[如何判断一个新配置是否会生效](#config-checklist)。**
- **配置项并不是手写白名单维护，而是自动从 `utils.config.py` 收集**。

---

## 4. 自动收集配置项的规则

当前系统不再手工维护 `CONFIG_KEYS` 白名单，而是从 `utils/config.py` 自动发现配置项。

自动发现规则如下：

一个变量会被当成“配置项”，必须同时满足：

- 变量名是全大写，例如 `CLIENT_TIMEOUT`
- 变量名**不能以下划线开头**，例如 `_SECRET` 不会被收集
- 变量值不能是可调用对象（callable），例如函数不会被收集

当前实现等价于下面这条规则：

```python
name.isupper() and not name.startswith("_") and not callable(value)
```

### 4.1 会被收集的例子

```python
CLIENT_TIMEOUT = 1800
LLM_SERVER_MODEL_NAME = ["demo_model"]
USE_NLP_FORMAT_RETURN = True
CHAT_PROFILE_CONFIGS = []
```

### 4.2 不会被收集的例子

```python
_client_timeout = 1800      # 以下划线开头，不收集
client_timeout = 1800       # 不是全大写，不收集
MixedCaseValue = 1          # 不是全大写，不收集

def BUILD_CONFIG():         # callable，不收集
    return {}
```

### 4.3 关于 `isupper()` 的注意事项

Python 的 `str.isupper()` 要求：

- 字母必须全部是大写
- 可以包含下划线和数字

所以这些名字都可以被收集：

```python
MODEL_V2_NAME = "a"
API_KEY_1 = "b"
LONG_REPORT_MAX_TOKENS = 4096
```

而这些不会被收集：

```python
Model_Name = "a"
api_key = "b"
LongReportMaxTokens = 4096
```

**建议统一使用 `UPPER_SNAKE_CASE` 命名。**

---

## 5. 三层配置优先级详解

### 5.1 第一层：JSON 配置（最高优先级）

系统会优先尝试读取 JSON 配置。

支持两种方式指定 JSON：

#### 方式 A：通过环境变量显式指定 JSON 路径

支持以下环境变量名：

- `S1_DR_CONFIG_JSON`
- `DR_SKILLS_CONFIG_JSON`
- `CONFIG_JSON_PATH`

示例：

```bash
export S1_DR_CONFIG_JSON=/path/to/config.json
```

如果给的是相对路径，例如：

```bash
export S1_DR_CONFIG_JSON=tmp/my_config.json
```

它会被解释为**相对于仓库根目录**的路径，而不是相对于任意 shell 当前目录。

#### 方式 B：不显式指定，使用默认搜索路径

如果没有显式设置上述环境变量，系统会按顺序查找以下文件：

- `config.local.json`
- `config.json`
- `utils/config/config.local.json`
- `utils/config/config.json`

注意：

- 搜索到第一个存在的文件后就会停止。
- 不会把多个 JSON 合并。
- 当前实现是“找到第一个有效 JSON 文件并加载”。

#### JSON 文件格式要求

JSON 顶层必须是一个对象（object），例如：

```json
{
  "CLIENT_TIMEOUT": 3600,
  "USE_NLP_FORMAT_RETURN": false
}
```

下面这种格式是错误的，因为顶层是数组：

```json
[
  {"CLIENT_TIMEOUT": 3600}
]
```

如果顶层不是对象，程序会抛出异常。

#### JSON 中的 key 命名要求

为了让 JSON 配置真正起作用，建议：

- key 与 `utils/config.py` 中的配置变量名保持**完全一致**
- 推荐使用全大写的 `UPPER_SNAKE_CASE`

例如：

`utils/config.py` 中是：

```python
MY_NEW_FLAG = "default"
```

那 JSON 中应写：

```json
{
  "MY_NEW_FLAG": "json_value"
}
```

不要写成：

```json
{
  "my_new_flag": "json_value"
}
```

后者虽然 JSON 能被读取，但因为业务代码不会访问 `my_new_flag`，通常不会产生你想要的效果。

### 5.2 第二层：环境变量

如果 JSON 没提供某个 key，系统会继续查环境变量。

对于任意配置项 `KEY`，系统会按顺序查找：

1. `KEY`
2. `S1_DR_KEY`
3. `DR_SKILLS_KEY`

例如配置项为：

```python
CLIENT_TIMEOUT = 1800
```

则会依次尝试：

- `CLIENT_TIMEOUT`
- `S1_DR_CLIENT_TIMEOUT`
- `DR_SKILLS_CLIENT_TIMEOUT`

先找到哪个，就使用哪个。

### 5.3 第三层：`utils/config.py` 默认值（最低优先级）

如果 JSON 和环境变量都没有给出某个配置项，就会回退到：

- `utils/config.py`

这是整个系统的默认值来源，也是自动发现配置项的来源。

---

## 6. 环境变量类型转换规则

环境变量本质上都是字符串，因此系统会根据 `utils/config.py` 里的默认值类型做自动转换。

这是一个很重要的细节：

- 类型推断**不是瞎猜**
- 而是参考 `config.py` 中该配置项的默认值类型

### 6.1 布尔值

如果默认值是 `bool`，支持以下写法：

```bash
export USE_NLP_FORMAT_RETURN=true
export USE_NLP_FORMAT_RETURN=false
export USE_NLP_FORMAT_RETURN=1
export USE_NLP_FORMAT_RETURN=0
export USE_NLP_FORMAT_RETURN=yes
export USE_NLP_FORMAT_RETURN=no
export USE_NLP_FORMAT_RETURN=on
export USE_NLP_FORMAT_RETURN=off
```

转换规则：

- `1`, `true`, `yes`, `on` -> `True`
- `0`, `false`, `no`, `off` -> `False`

大小写会先统一转成小写再判断。

### 6.2 整数

如果默认值是 `int`，会执行：

```python
int(raw_value)
```

例如：

```bash
export CLIENT_TIMEOUT=3600
```

### 6.3 浮点数

如果默认值是 `float`，会执行：

```python
float(raw_value)
```

### 6.4 列表

如果默认值是 `list`，优先按 JSON 解析；如果解析后不是列表，则退化成“逗号分隔”。

例如下面两种都可以：

```bash
export LLM_SERVER_MODEL_NAME='["model_a", "model_b"]'
```

或者：

```bash
export LLM_SERVER_MODEL_NAME=model_a,model_b
```

### 6.5 字典

如果默认值是 `dict`，那么环境变量值必须是合法 JSON 对象。

例如：

```bash
export SOME_DICT='{"a": 1, "b": 2}'
```

如果不是合法 JSON 对象，会抛出异常。

### 6.6 字符串

如果默认值不是上述类型，则保持原字符串。

---

## 7. 推荐使用方式

### 7.1 最推荐：默认值放 `config.py`，真实环境配置放 JSON

推荐原因：

- 真实环境配置可以与代码分离
- 便于本地、测试、线上使用不同 JSON
- 私有配置不必硬编码进仓库

推荐模式：

1. 在 `utils/config.py` 里定义默认值
2. 在某个 JSON 文件中写真实覆盖值
3. 通过 `S1_DR_CONFIG_JSON` 指向该 JSON

例如：

```python
# utils/config.py
MY_NEW_FLAG = "default"
```

```json
{
  "MY_NEW_FLAG": "prod"
}
```

```bash
export S1_DR_CONFIG_JSON=/path/to/my_config.json
python your_eval_entry.py
```

### 7.2 适合临时调试：环境变量覆盖

例如只想临时改一个参数：

```bash
export CLIENT_TIMEOUT=7200
python your_eval_entry.py
```

这种方式适合：

- 临时实验
- CI 中临时注入参数
- shell 启动脚本里少量覆盖

不太适合：

- 结构复杂的长配置
- 多 profile 管理
- 团队共享配置模板

### 7.3 业务代码中的推荐 import 写法

如果你只是普通启动一次进程，下面两种都可以：

```python
from utils.configs import CLIENT_TIMEOUT
```

```python
import utils.configs as configs
print(configs.CLIENT_TIMEOUT)
```

但如果你希望在运行时使用 `reload_config()` 动态刷新，**更推荐第二种**：

```python
import utils.configs as configs

configs.reload_config()
print(configs.CLIENT_TIMEOUT)
```

因为：

```python
from utils.configs import CLIENT_TIMEOUT
```

在很多情况下会把值绑定为导入时的局部变量，后面即使 reload，当前模块中的这个局部名也不一定自动变化。

---

## 8. `reload_config()` 的用途和边界

`reload_config()` 的作用是：

- 重新读取 `utils.config`
- 重新自动发现大写配置项
- 重新扫描 JSON 配置路径
- 重新读取环境变量
- 刷新 `utils.configs` 模块中暴露的配置变量

典型场景：

- 你在长生命周期进程中临时改了环境变量
- 你切换了 `S1_DR_CONFIG_JSON`
- 你刚刚修改了 `utils/config.py`，想在当前解释器里重新生效

调用方式：

```python
import utils.configs as configs
configs.reload_config()
```

### 8.1 对“新增配置项”的效果

如果你新增了：

```python
NEW_SETTING = 123
```

然后执行：

```python
configs.reload_config()
```

那么新的配置项会被自动纳入配置系统。

### 8.2 对“删除配置项”的效果

如果你从 `utils/config.py` 删除了某个原有大写变量，调用 `reload_config()` 后：

- 它会从自动收集结果中消失
- `utils.configs` 中旧的同名全局变量也会被清理
- 再访问会触发 `AttributeError`

### 8.3 一个重要限制

如果其他模块已经这样写了：

```python
from utils.configs import CLIENT_TIMEOUT
```

并且这个 import 已经发生，那么该模块内的 `CLIENT_TIMEOUT` 很可能是导入时拷贝下来的值。

即使后面执行：

```python
configs.reload_config()
```

这个其他模块内部的局部变量也不一定自动更新。

这属于 Python import 机制本身的语义，不是本系统独有的问题。

所以：

- 对一次性启动的评测脚本：通常直接重启进程最稳妥
- 对需要热更新的场景：推荐统一使用 `import utils.configs as configs`

---

## 9. 常见使用示例

### 9.1 只用默认值

`utils/config.py`：

```python
MY_BATCH_SIZE = 8
```

代码：

```python
from utils.configs import MY_BATCH_SIZE
print(MY_BATCH_SIZE)
```

输出：

```python
8
```

### 9.2 用环境变量覆盖

`utils/config.py`：

```python
MY_BATCH_SIZE = 8
```

启动前：

```bash
export MY_BATCH_SIZE=32
```

程序读取到的是：

```python
32
```

### 9.3 用 JSON 覆盖

`utils/config.py`：

```python
MY_BATCH_SIZE = 8
```

JSON：

```json
{
  "MY_BATCH_SIZE": 64
}
```

启动前：

```bash
export S1_DR_CONFIG_JSON=/path/to/config.json
```

程序读取到的是：

```python
64
```

### 9.4 JSON 优先级高于环境变量

如果：

```bash
export MY_BATCH_SIZE=32
export S1_DR_CONFIG_JSON=/path/to/config.json
```

并且 JSON 中：

```json
{
  "MY_BATCH_SIZE": 64
}
```

最终结果是：

```python
64
```

因为 JSON 优先级更高。

---

<a id="developer-guide"></a>

## 10. 开发者维护指南

这一节专门从开发者视角说明：后续怎样新增、删除、重构和排查配置项。

### 10.1 新增配置项的标准流程

假设你想新增一个配置项：`MY_NEW_FLAG`

#### 第一步：在 `utils/config.py` 中定义默认值

```python
MY_NEW_FLAG = "default_value"
```

命名建议：

- 使用 `UPPER_SNAKE_CASE`
- 不以下划线开头
- 不要定义成函数

#### 第二步：如果需要，更新示例文件

建议同步更新：

- `utils/config/config.example.json`
- 如果需要，也可以补充当前文档中的例子

例如：

```json
{
  "MY_NEW_FLAG": "example_value"
}
```

#### 第三步：在业务代码中读取

```python
from utils.configs import MY_NEW_FLAG
```

或者：

```python
import utils.configs as configs
print(configs.MY_NEW_FLAG)
```

#### 第四步：如果在当前进程内调试，记得 reload

```python
import utils.configs as configs
configs.reload_config()
```

#### 第五步：如果是正式脚本，最稳妥是重启进程

例如重新执行评测入口脚本，而不是依赖热更新。

### 10.2 删除配置项的标准流程

假设你想删除 `OLD_FLAG`

步骤如下：

1. 从 `utils/config.py` 中删除 `OLD_FLAG`
2. 删除 JSON 示例中对应的条目
3. 全局搜索仓库中是否还有引用：

```bash
rg "OLD_FLAG" repo/s1-dr-skills-v3
```

4. 清理这些引用
5. 重新启动相关脚本，或在调试环境里执行 `reload_config()`

注意：

- 如果业务代码里还有 `from utils.configs import OLD_FLAG`，删除后会报错
- 这是预期行为，因为该配置项已经不存在了

### 10.3 修改已有配置项类型时的注意事项

例如你原来是：

```python
MY_SETTING = "1,2,3"
```

后来改成：

```python
MY_SETTING = [1, 2, 3]
```

这会影响环境变量的解析逻辑，因为环境变量类型推断依赖默认值类型。

因此修改配置项类型时，要同步检查：

- `config.example.json` 是否仍然合理
- 启动脚本中的环境变量是否还能正确解析
- 业务代码是否仍按新类型使用

### 10.4 不建议的做法

以下做法不推荐：

#### 不建议 1：在 `config.py` 中定义大量临时大写常量

因为所有符合规则的大写变量都会自动进入配置系统。

如果某个值只是模块内部常量，不希望变成“正式配置项”，不要写成会被自动收集的形式。

比如不要这样：

```python
TEMP_DEBUG_MARKER = "abc"
```

如果它并不是你想暴露给全仓库的配置。

可以改成：

```python
_temp_debug_marker = "abc"
```

或者：

```python
temp_debug_marker = "abc"
```

#### 不建议 2：依赖拼错 key 的 JSON 配置

例如 `config.py` 中是：

```python
CLIENT_TIMEOUT = 1800
```

但 JSON 写成：

```json
{
  "CLIENT-TIMEOUT": 3600
}
```

这种拼写不一致通常不会达到预期效果。

#### 不建议 3：把复杂结构随意塞进环境变量

环境变量适合少量覆盖，不太适合特别大的嵌套配置对象。

复杂对象更适合放 JSON。

### 10.5 推荐的维护原则

建议遵循以下原则：

- 默认值统一放 `utils/config.py`
- 真实环境配置优先放 JSON
- 临时实验用环境变量
- 配置名统一使用 `UPPER_SNAKE_CASE`
- 不以 `_` 开头，除非明确不想让它进入配置系统
- 修改配置项类型时，检查环境变量解析影响
- 删除配置项前，先全局搜索引用
- 需要热更新时，用 `import utils.configs as configs`

---

<a id="config-checklist"></a>

## 11. 如何判断一个新配置是否会生效

如果你新增了一个配置项，可以按这个 checklist 检查：

1. 它是否定义在 `utils/config.py`
2. 名字是否全大写
3. 是否没有以下划线开头
4. 是否不是函数或其他 callable
5. JSON 中的 key 是否与变量名完全一致
6. 业务代码是否真的读取了这个配置项
7. 是否是新启动的进程，或者已经执行了 `reload_config()`

只要这些条件都满足，它通常就会生效。

---

## 12. 排查问题时的建议

### 问题 1：为什么 JSON 配置没有生效？

排查顺序：

1. 是否真的设置了 `S1_DR_CONFIG_JSON`
2. 路径是否正确
3. JSON 是否是合法对象
4. JSON 中的 key 是否与 `config.py` 完全一致
5. 业务代码是否访问的是同一个名字
6. 是否其实被另一个更前面的 JSON 文件抢先匹配了

### 问题 2：为什么新增配置项没有生效？

排查顺序：

1. 变量名是不是全大写
2. 是否以下划线开头
3. 是否只是改了文件但没有重启进程
4. 是否需要调用 `reload_config()`
5. 业务代码是否真的 import/访问了该变量

### 问题 3：为什么删掉配置项后还能访问？

通常原因有两个：

1. 进程还没 reload / 重启
2. 某个模块之前已经 `from utils.configs import XXX`，把旧值绑定下来了

---

## 13. 一句话总结

当前配置系统的核心原则是：

- **配置项来源于 `utils/config.py` 中符合规则的大写变量**
- **最终取值遵循 `JSON > 环境变量 > config.py`**
- **对外统一从 `utils.configs` 访问**
- **新增/删除配置项主要维护 `utils/config.py`，并按需重启或 reload**

如果你后续继续维护这套系统，最重要的三条经验是：

1. 新配置名请用 `UPPER_SNAKE_CASE`
2. 不想暴露成配置项的变量，不要写成“全大写且不以下划线开头”
3. 动态变更配置时，优先理解 Python import 的静态绑定语义
