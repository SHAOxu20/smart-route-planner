#!/bin/bash
# LocalSmartRoute 一键启动脚本

echo "=========================================="
echo "  LocalSmartRoute 智能路线规划系统"
echo "=========================================="

# 启动后端
echo "[1/2] 启动后端服务 (port 8000)..."
cd "$(dirname "$0")/backend"
pip install -r requirements.txt -q 2>/dev/null
python main.py &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"

# 等待后端就绪
sleep 2

# 启动前端
echo "[2/2] 启动前端开发服务器 (port 3000)..."
cd "$(dirname "$0")/frontend"
npm run dev &
FRONTEND_PID=$!
echo "  前端 PID: $FRONTEND_PID"

echo ""
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:8000"
echo "  API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
