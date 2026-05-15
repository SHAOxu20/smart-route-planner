# LocalSmartRoute 智能路线规划

基于自然语言的全国范围智能路线规划系统，支持手机端实时 GPS 定位 + 动态路线生成。

## 名词定义

| 术语 | 含义 | 适用端 |
|------|------|--------|
| **IP** | 电脑端网络 IP 地址，仅代表电脑端网络出口位置 | 电脑 |
| **GPS** | 手机端本机定位（GNSS/BDS + 基站 + WiFi），仅代表手机端真实地理位置 | 手机 |

> **定位串位说明**：该问题仅发生在电脑端（依赖 IP 识别位置时产生偏差）。手机端走本机 GPS 定位，不受 IP 影响，不会触发串位。

---

## 技术架构

```
用户输入 (自然语言/语音)
    │
    ▼
┌──────────────────────────────────┐
│  前端 (React + Vite + Tailwind)  │
│  · 高德地图实时标注               │
│  · 手机 GPS 自动定位              │
│  · PWA 可安装到桌面               │
│  · 语音输入 (Web Speech API)      │
└──────────────┬───────────────────┘
               │ HTTPS
               ▼
┌──────────────────────────────────┐
│  后端 (FastAPI + SQLite)          │
│  · 意图解析 (规则引擎 + LLM)       │
│  · 多维度 POI 搜索 (高德 API)      │
│  · 路线规划 (A/B/C 三套方案)       │
│  · 天气约束 (和风天气)             │
│  · 用户历史 + 动态调整             │
└──────────────┬───────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌──────────┐    ┌──────────────┐
│ 高德地图  │    │ Ollama / LLM │
│ POI搜索   │    │ 意图解析     │
│ 逆地理编码 │    │ 路线描述润色  │
└──────────┘    └──────────────┘
```

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- Ollama (可选，用于 LLM 增强)

### 后端启动

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 填入高德 API Key
python main.py         # http://localhost:8000
```

### 前端开发

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

### 生产构建

```bash
cd frontend && npm run build
cd ../backend && python main.py   # 后端自动 serve 前端静态文件
```

## 主要功能

- **自然语言输入**：任意描述出行需求，无预设场景限制
- **手机 GPS 定位**：高德 GNSS/BDS + 浏览器定位并行竞速
- **A/B/C 三套路线**：体验优先 / 性价比 / 高效紧凑
- **动态调整**：口语化反馈即时重规划（"太贵了""加个咖啡店""时间来不及"）
- **天气约束**：实时天气数据，雨天自动推荐室内场所
- **PWA 支持**：手机浏览器可安装到桌面，接近原生体验

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/route/plan` | 主规划接口 |
| POST | `/api/route/adjust` | 动态调整 |
| POST | `/api/route/describe` | AI 润色方案描述 |
| GET | `/api/weather?city=xx` | 天气查询 |
| GET | `/api/pois?keyword=xx&city=xx` | POI 搜索 |
| GET | `/api/history/{session_id}` | 用户历史 |
| GET | `/api/health` | 健康检查 |

## License

MIT
