# TTS 语音生成 — 经验文档

> 本文档记录文字转语音（TTS）的各种实现方式、认证方法、工具路径与避坑指南。
> 由 Fanli 整理，2026-04-05 验证通过。

---

## 核心概念

TTS（Text-to-Speech）即"文字转语音"，流程本质上是：

```
文字输入 → TTS API / 工具 → 音频文件（MP3/WAV/OGG）
```

三种主流方式对比：

| | Microsoft Edge TTS | MiniMax API | OpenAI TTS |
|---|---|---|---|
| **费用** | 免费（微软 Edge 神经网络语音） | TokenPlan 额度内免费 | 付费 |
| **质量** | 高（Neural 级别） | 极高（speech-2.8-hd） | 高 |
| **中文支持** | ✅ 优秀 | ✅ 优秀 | ✅ 优秀 |
| **免 API Key** | ✅ 无需 | ❌ 需要 | ❌ 需要 |
| **调用难度** | 低（Node.js 类库） | 低（Python requests） | 低 |
| **OpenClaw 集成** | ✅（via node-edge-tts） | ✅（via Python 脚本） | ⚠️ 需配置 |

---

## 方式一：Microsoft Edge TTS（当前生产主力）

### 为什么用它
- 完全免费，无需任何 API key
- 已集成在 OpenClaw 全局 node_modules（`node-edge-tts`）
- 中文 Neural 语音质量优秀（`zh-CN-XiaoxiaoNeural` 等）
- 适合日常大量使用场景

### 技术路径

**Node.js 类库（直接调用，非 CLI）：**
```javascript
// EdgeTTS 类在 OpenClaw 全局 node_modules 中
const {EdgeTTS} = require('/opt/homebrew/lib/node_modules/openclaw/node_modules/node-edge-tts/dist/edge-tts.js');

const tts = new EdgeTTS({
    voice: 'zh-CN-XiaoxiaoNeural',    // 音色
    lang: 'zh-CN',
    outputFormat: 'audio-24khz-48kbitrate-mono-mp3',
    rate: '+0%',                      // 语速
    pitch: '+0Hz',                    // 音高
    proxy: ''
});

tts.ttsPromise('要转换的文字', '/path/to/output.mp3')
    .then(() => console.log('SUCCESS'))
    .catch(err => console.error('ERROR:', err.message));
```

**Python 包装脚本（推荐使用）：**
```python
import subprocess, os, json

EDGE_TTS_MODULE = "/opt/homebrew/lib/node_modules/openclaw/node_modules/node-edge-tts/dist/edge-tts.js"

def synthesize(text, output_path, voice="zh-CN-XiaoxiaoNeural", rate="+0%"):
    node_script = f"""
const {{EdgeTTS}} = require('{EDGE_TTS_MODULE}');
const tts = new EdgeTTS({{
    voice: '{voice}', lang: 'zh-CN',
    outputFormat: 'audio-24khz-48kbitrate-mono-mp3',
    rate: '{rate}', pitch: '+0Hz', proxy: ''
}});
tts.ttsPromise({json.dumps(text)}, '{output_path}')
    .then(() => {{ console.log('SUCCESS'); process.exit(0); }})
    .catch(err => {{ console.error('TTS_ERROR:' + err.message); process.exit(1); }});
"""
    subprocess.run(['node', '--eval', node_script], timeout=180)
```

**脚本位置：** `/Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py`
（注意：文件名历史原因，实际包含 Microsoft TTS 和 MiniMax TTS 两种模式）

### 常用音色推荐

| 音色 ID | 说明 |
|---|---|
| `zh-CN-XiaoxiaoNeural` | 女声晓晓（推荐，日常使用） |
| `zh-CN-XiaoyiNeural` | 女声小艺 |
| `zh-CN-YunxiNeural` | 男声云希（推荐） |
| `zh-CN-YunyangNeural` | 男声云扬（新闻风格） |
| `zh-CN-YunzeNeural` | 男声云泽 |
| `en-US-JennyNeural` | 英文女声 |
| `en-US-GuyNeural` | 英文男声 |

### 避坑提示

- ❌ 不要用 CLI 方式调用（`bin.js` 有 yargs ESM 兼容性问题，会报错 `require is not defined in ES module scope`）
- ✅ 必须直接 `require` 导入 `dist/edge-tts.js` 类
- ✅ proxy 参数传空字符串 `''` 而非 `None`
- ⚠️ Edge TTS 是微软 Edge 浏览器的云端神经网络语音，走的是微软全球 CDN，中国大陆访问可能需要代理

---

## 方式二：MiniMax API TTS（备用 / 高质量场景）

### 为什么保留它
- TokenPlan 包含 TTS 额度（Plus: 4000 字符/天）
- `speech-2.8-hd` 音质极高，支持情感控制
- 音色库丰富（200+ 音色，支持中英双语）
- 不走微软 CDN，中国大陆访问更稳定

### API 信息

| 项目 | 值 |
|---|---|
| **端点** | `https://api.minimaxi.com/v1/t2a_v2`（中国大陆版） |
| **备用端点** | `https://api.minimax.io/v1/t2a_v2`（国际版） |
| **备用端点 2** | `https://api-bj.minimaxi.com/v1/t2a_v2`（北京节点） |
| **认证** | `Authorization: Bearer <TokenPlan Key>` |
| **Key 格式** | `sk-cp-xxxxxxxx`（TokenPlan 专属 key） |
| **是否需要 GroupId** | ❌ 不需要（测试证明：加 GroupId 反而报错） |
| **模型** | `speech-2.8-hd`（推荐）/ `speech-02-hd` / `speech-01-hd` |

### 核心请求格式

```python
import urllib.request, json, binascii

token = "sk-cp-你的TokenPlanKey"
payload = {
    "model": "speech-2.8-hd",
    "text": "要转换的文字",
    "stream": False,
    "voice_setting": {
        "voice_id": "male-qn-qingse",  # 音色 ID
        "speed": 1.0,                   # 语速 0.5-2.0
        "vol": 1.0,                     # 音量
        "pitch": 0                      # 音高
    },
    "audio_setting": {
        "sample_rate": 32000,
        "bitrate": 128000,
        "format": "mp3",
        "channel": 1
    }
}
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "https://api.minimaxi.com/v1/t2a_v2",
    data=data, headers=headers, method="POST"
)
with urllib.request.urlopen(req, timeout=120) as resp:
    result = json.loads(resp.read().decode("utf-8"))
    audio_bytes = binascii.unhexlify(result["data"]["audio"])
    with open("output.mp3", "wb") as f:
        f.write(audio_bytes)
```

### 认证文件

认证信息读取顺序：
1. 环境变量 `MINIMAX_API_KEY`
2. 文件 `~/.minimax/tts_config.json`

```json
{
  "api_key": "sk-cp-你的TokenPlanKey",
  "group_id": "（已废弃，无需填写）"
}
```

### 常用音色推荐

| 音色 ID | 说明 |
|---|---|
| `male-qn-qingse` | 男声青少（**推荐**，音质好） |
| `male-qn-qingse2` | 男声青少2 |
| `female-qn-qingse` | 女声青少 |
| `female-qn-yisu` | 女声逸群 |
| `Chinese (Mandarin)_Radio_Host` | 中文电台主播 |
| `English_Expressive_Narrator` | 英文旁白 |

完整音色列表：访问 `https://platform.minimaxi.com/docs/api-reference/speech-t2a-http`

### 避坑提示

- ❌ **不要用国际版端点** `api.minimax.io` + TokenPlan key，会返回 2049（invalid api key）
- ✅ 中国大陆用户必须用 `api.minimaxi.com`
- ❌ **不要带 GroupId header**，实测带 GroupId 会导致 1004 错误
- ✅ Authorization 格式：`Bearer sk-cp-xxx`，**Bearer 前缀必须有**
- ❌ TokenPlan key 不支持普通文本 API（会 401），但**支持 TTS API**（已验证）
- ⚠️ 每次调用消耗字符数 = 实际文字字数 × 1.5~2.0（标点、停顿也会计入）
- ⚠️ 文字超长（>3000 字符）建议用流式模式 `stream: True`，或分段调用

### 错误码参考

| 错误码 | 含义 | 解决方案 |
|---|---|---|
| `2049` | invalid api key | 确认用 `api.minimaxi.com` 而非 `api.minimax.io` |
| `1004` | login fail（认证格式错） | 确认 `Authorization: Bearer sk-cp-xxx`（无 GroupId） |
| `1002` | rate limit | 降低频率，等几秒再试 |

---

## 方式三：OpenAI TTS（未集成，了解即可）

```python
import openai, os

client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
with client.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="alloy",
    input="要转换的文字"
) as resp:
    resp.stream_to_file("output.mp3")
```

**状态：** OpenAI API Key 已失效（401），未配置，不可用。

---

## 在工作流中的使用方式

### 每日早报（当前生产）

**使用 Microsoft Edge TTS**，路径：`/Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py`

```python
# 实际 cron job 调用的命令：
python3 /Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py \
  --file /tmp/news_briefing_script.txt \
  /tmp/news_audio_today.mp3 \
  --voice zh-CN-XiaoxiaoNeural
```

### 备用方案（MiniMax TTS）

如需切换，将 `--voice` 参数改为 MiniMax 音色，并确保脚本使用 MiniMax 端点：

```python
# MiniMax TTS 调用（在同一脚本内，通过 --provider 参数切换）
# （如需实现，修改 minimax_tts.py 的 provider 参数）
```

---

## 文件路径速查

```
TTS 相关文件
├── 工具脚本
│   └── /Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py
│       （统一入口，支持 Microsoft TTS 和 MiniMax TTS）
│
├── Microsoft Edge TTS
│   ├── 类库：/opt/homebrew/lib/node_modules/openclaw/node_modules/node-edge-tts/dist/edge-tts.js
│   ├── CLI：/opt/homebrew/lib/node_modules/openclaw/node_modules/node-edge-tts/bin.js（❌ 有兼容问题）
│   └── 音色参考：https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-text-to-speech
│
├── MiniMax TTS
│   ├── API 文档：https://platform.minimaxi.com/docs/api-reference/speech-t2a-http
│   ├── 认证配置：~/.minimax/tts_config.json
│   ├── 端点：https://api.minimaxi.com/v1/t2a_v2
│   └── 音色列表：https://platform.minimaxi.com/docs/api-reference/speech-t2a-http
│
└── 经验文档
    └── /Users/unclejoe/Doc_Workspace/ai-daily-news/knowledge/TTS.md（本文件）
```
