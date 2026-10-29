# CrypTool 2 简体中文语言包

将 [CrypTool 2](https://www.cryptool.org/en/ct2/) 的界面与插件文本本地化为简体中文（`zh-CN`）。

采用 .NET 标准的**卫星资源程序集**（satellite assembly）机制：不修改任何原始二进制，
只在 `zh-CN` 目录下新增一批 `*.resources.dll`，由 .NET 运行时按当前界面语言自动加载。

---

## 目录结构

```
cryptool-zh/
├─ data/                  # 中间数据与可校对表格
│  ├─ strings.json        # 从德语卫星程序集抽取的全部字符串
│  ├─ by-assembly.json    # 同上，按程序集分组
│  ├─ glossary.json       # 德→中 术语表（含保留原名的专有名词）
│  ├─ translation-cache.json   # 德→中 翻译缓存（键为德语原文）
│  ├─ translation-table.csv    # ★ 人可读对照表（UTF-8 BOM，Excel 可直接打开）
│  ├─ translation-table.json   # 同上，结构化版本
│  └─ stats.json          # 覆盖率统计
├─ scripts/
│  ├─ extract.ps1         # 从 de 卫星程序集抽取字符串
│  ├─ translate.py        # 批量机翻 + 术语约束 + HTML/占位符保护
│  ├─ rebuild.ps1         # 生成 zh-CN 卫星程序集
│  └─ make-tables.py      # 生成对照表与统计
└─ out/
   └─ zh-CN/              # ★ 产出物：可直接覆盖到安装目录
      ├─ zh-CN/*.resources.dll            # 主程序及核心库
      ├─ CrypPlugins/zh-CN/*.resources.dll # 插件
      └─ Lib/zh-CN/*.resources.dll         # 第三方库外壳
```

---

## 安装方法

1. **完全关闭 CrypTool 2**（包括托盘图标）。
2. 备份原始安装目录（建议整个复制一份）。
3. 将 `out/zh-CN/` 下的内容**按相同相对路径**复制进 CrypTool 2 安装目录：

   ```
   out\zh-CN\zh-CN\*.resources.dll              ->  <安装目录>\zh-CN\
   out\zh-CN\CrypPlugins\zh-CN\*.resources.dll  ->  <安装目录>\CrypPlugins\zh-CN\
   out\zh-CN\Lib\zh-CN\*.resources.dll          ->  <安装目录>\Lib\zh-CN\
   ```

4. 启动 CrypTool 2，在设置中把界面语言切换为中文
   （`Einstellungen → Sprache` / `Settings → Language`）。

**卸载**：删除上述三个 `zh-CN` 目录即可，原始文件未被改动。

---

## 技术说明

### 为什么不需要逆向二进制

CrypTool 2 是 .NET (WPF) 应用，其文本存放在标准 `ResourceManager` 二进制资源中：

- **英语**：内嵌在主程序集（`CrypWin.exe` 等）里
- **德语**：独立的卫星程序集 `de\*.resources.dll`

本项目以**德语**为翻译源（德语资源完整且为官方维护），读取其中的
`.resources` 流，替换字符串值，再重新编译为 `zh-CN\*.resources.dll`。

### 资源命名规则（关键）

`ResourceManager` 依据嵌入资源名中的**文化后缀**定位语言资源。因此：

```
原始:  CrypTool.CrypWin.Properties.Resources.de.resources
生成:  CrypTool.CrypWin.Properties.Resources.zh-CN.resources
```

同时程序集本身需带 `[assembly: AssemblyCulture("zh-CN")]`，否则运行时不会在
`zh-CN` 子目录中探测它。

### 必须保留的内容

| 内容 | 处理方式 |
|---|---|
| `{0}` `{1}` 等占位符 | 原样保留，逐条校验 |
| HTML 标签（90 条含标记，含完整 HTML 文档） | 原样保留，仅翻译文本节点 |
| `Bitmap` / `Icon` 资源（42 条） | **二进制原样复制**，不参与翻译 |
| 专有名词（AES、RSA、Achterbahn 等） | 保留拉丁原名，见 `glossary.json` |

### PE 架构一致性

原始德语卫星程序集是 **PE32+ / x86_64**。若用默认 AnyCPU 目标编译，
产出的是 x86 PE32，与原始程序集架构不符，CLR 会拒绝加载。
因此 `rebuild.ps1` 会读取源程序集的 PE machine 字段并据此选择
`/platform:x64` 或 `/platform:x86`。

---

## 重新生成

环境要求：Windows + .NET Framework 4.x（含 `csc.exe`）+ Python 3.9+。

```powershell
# 1. 抽取德语字符串
powershell -ExecutionPolicy Bypass -File scripts\extract.ps1

# 2. 翻译（可中断；进度保存在 translation-cache.json）
python scripts\translate.py

# 3. 生成 zh-CN 卫星程序集
powershell -ExecutionPolicy Bypass -File scripts\rebuild.ps1

# 4. 生成对照表
python scripts\make-tables.py
```

`translate.py` 支持 `--limit N` 做小批量试跑，`--sleep` 控制请求间隔。

---

## 校订翻译

1. 打开 `data/translation-table.csv`（UTF-8 BOM）。
2. 直接修改 `chinese` 列。
3. 把改动同步回 `data/translation-cache.json`
   （键 = `german` 列原文，值 = 修改后的中文），或重新跑一次
   `make-tables.py` 之前手工合并。
4. 重新执行 `rebuild.ps1` 即可。

术语统一请修改 `data/glossary.json` 的 `terms` 数组后重新翻译；
该表在**翻译前**将德语术语替换为受保护标记，因此能锁定译法，
而非事后替换（事后替换只能改动机器翻译已产出、且已被译错的词）。

---

## 本次产出统计

| 项目 | 数值 |
|---|---|
| 翻译引擎 | 德语 → 简体中文（机器翻译 + 术语约束 + 人工规则修正） |
| 卫星程序集 | **207 个**（全部重新编译） |
| 可翻译字符串 | **9,350 条** |
| 已翻译 | **9,350 条（100%）** |
| 空源文本（无需翻译） | 9 条 |
| 回退德语 | **0 条** |
| 非字符串资源（Bitmap/Icon） | 42 条，二进制原样保留 |
| 输出体积 | 1.9 MB |

覆盖率 100% 指**资源表内**可翻译文本；运行时拼接或硬编码字符串不在其中（见下）。

## 已知限制

- 机器翻译起步，专业表述与长句仍建议人工校对；`stats.json` 给出实际覆盖率。
- 少量 HTML 帮助文档条目只翻译了正文，内嵌 CSS/脚本未改动。
- 无法翻译**运行时拼接**的字符串（代码中 `"前缀" + 变量` 形式），
  这类文本不在资源表中。
- 仅覆盖资源表内的文本；硬编码在源码里的字符串（如部分错误消息）不在其中。
- 未修改、未反编译任何原始程序集的 IL 代码。

---

## 许可与声明

- CrypTool 2 本身由 CrypTool 项目组按 **Apache License 2.0** 发布
  （见其官网与随附 `license.txt`）。
- 本项目仅新增语言资源程序集，**不包含** CrypTool 2 的原始二进制、
  源码或商标素材；分发时请自行遵守上游许可条款。
- 本项目与 CrypTool 项目组无隶属关系，非官方语言包。
- 翻译文本为社区贡献，按 CC BY 4.0 提供，欢迎修订。
