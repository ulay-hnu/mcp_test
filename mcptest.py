# app.py
from flask import Flask, render_template, request, jsonify
import requests
import os
import json
import subprocess
import time
import threading
import signal
import sys
import atexit
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 创建应用时传入需要的参数
app = Flask(__name__)

# 获取OpenRouter API密钥(从环境变量中)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# MCP服务器配置
MCP_SERVERS = {
    "playwright": {
        "command": "cmd",
        "args": ["/c", "npx", "@playwright/mcp@latest"],
        "url": "http://localhost:3001/v1",  # Playwright MCP 默认端口
        "process": None
    },
    "desktop-commander": {
        "command": "cmd",
        "args": [
            "/c", "npx", "-y", "@smithery/cli@latest", "install",
            "@wonderwhy-er/desktop-commander", "--client", "cursor",
            "--key", "eb24917f-a13c-410c-9c5d-5fce0af3ef34"
        ],
        "url": "http://localhost:3000/v1",  # Desktop Commander 默认端口
        "process": None
    },
    "server-sequential-thinking": {
        "command": "cmd",
        "args": [
            "/c", "npx", "@smithery/cli@latest", "run",
            "@smithery-ai/server-sequential-thinking@latest", "--config", "{}"
        ],
        "url": "http://localhost:3002/v1",  # Sequential Thinking 默认端口
        "process": None
    }
}

# 存储MCP服务器状态
mcp_servers_status = {name: False for name in MCP_SERVERS.keys()}


# 使用 with app.app_context() 替代 @app.before_first_request
def init_mcp_servers():
    """初始化MCP服务器"""
    print("初始化MCP服务器...")
    start_all_mcp_servers()


def start_mcp_server(server_name):
    """启动指定的MCP服务器"""
    if server_name not in MCP_SERVERS:
        print(f"未知的MCP服务器: {server_name}")
        return False

    server_config = MCP_SERVERS[server_name]
    if server_config["process"] is not None and server_config["process"].poll() is None:
        print(f"{server_name} MCP服务器已在运行")
        return True

    try:
        print(f"启动 {server_name} MCP服务器...")
        process = subprocess.Popen(
            [server_config["command"]] + server_config["args"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        server_config["process"] = process

        # 等待服务器启动
        time.sleep(5)  # 简单等待5秒，实际应用中可能需要更复杂的检查
        mcp_servers_status[server_name] = True
        print(f"{server_name} MCP服务器已启动")
        return True
    except Exception as e:
        print(f"启动 {server_name} MCP服务器失败: {e}")
        return False


def stop_mcp_server(server_name):
    """停止指定的MCP服务器"""
    if server_name not in MCP_SERVERS:
        print(f"未知的MCP服务器: {server_name}")
        return

    server_config = MCP_SERVERS[server_name]
    if server_config["process"] is not None:
        print(f"停止 {server_name} MCP服务器...")
        try:
            # 在Windows上，用CTRL+C发送信号
            if os.name == 'nt':
                server_config["process"].terminate()
            else:
                server_config["process"].send_signal(signal.SIGINT)

            server_config["process"].wait(timeout=5)
            server_config["process"] = None
            mcp_servers_status[server_name] = False
            print(f"{server_name} MCP服务器已停止")
        except Exception as e:
            print(f"停止 {server_name} MCP服务器失败: {e}")
            if server_config["process"] is not None:
                server_config["process"].kill()
                server_config["process"] = None


def start_all_mcp_servers():
    """启动所有MCP服务器"""
    for server_name in MCP_SERVERS.keys():
        threading.Thread(target=start_mcp_server, args=(server_name,)).start()


def stop_all_mcp_servers():
    """停止所有MCP服务器"""
    for server_name in MCP_SERVERS.keys():
        stop_mcp_server(server_name)


# 应用退出时停止所有MCP服务器
def cleanup():
    """应用退出时的清理工作"""
    stop_all_mcp_servers()


# 注册退出处理函数
atexit.register(cleanup)


@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')


@app.route('/api/mcp-status')
def mcp_status():
    """返回MCP服务器状态"""
    return jsonify(mcp_servers_status)


@app.route('/api/start-mcp/<server_name>', methods=['POST'])
def start_mcp_api(server_name):
    """API端点用于启动指定的MCP服务器"""
    if server_name not in MCP_SERVERS:
        return jsonify({"error": f"未知的MCP服务器: {server_name}"}), 404

    success = start_mcp_server(server_name)
    if success:
        return jsonify({"status": "success", "message": f"{server_name} MCP服务器已启动"})
    else:
        return jsonify({"status": "error", "message": f"无法启动 {server_name} MCP服务器"}), 500


@app.route('/api/stop-mcp/<server_name>', methods=['POST'])
def stop_mcp_api(server_name):
    """API端点用于停止指定的MCP服务器"""
    if server_name not in MCP_SERVERS:
        return jsonify({"error": f"未知的MCP服务器: {server_name}"}), 404

    stop_mcp_server(server_name)
    return jsonify({"status": "success", "message": f"{server_name} MCP服务器已停止"})


@app.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    data = request.json
    messages = data.get('messages', [])
    model = data.get('model', 'anthropic/claude-3.7-sonnet')  # 默认模型
    selected_mcp = data.get('selected_mcp', None)  # 用户选择的MCP服务器

    try:
        # 如果选择了MCP服务器，先发送到该服务器处理
        mcp_result = None
        if selected_mcp and selected_mcp in MCP_SERVERS:
            server_config = MCP_SERVERS[selected_mcp]

            # 检查服务器是否运行
            if not mcp_servers_status[selected_mcp]:
                # 尝试启动服务器
                success = start_mcp_server(selected_mcp)
                if not success:
                    return jsonify({
                        "error": f"无法启动 {selected_mcp} MCP服务器"
                    }), 500

            try:
                # 根据不同的MCP服务器准备请求
                if selected_mcp == "playwright":
                    # Playwright MCP 请求格式
                    mcp_payload = {
                        "query": messages[-1]['content'],
                        "action": "analyze"  # 或其他适合的动作
                    }
                elif selected_mcp == "desktop-commander":
                    # Desktop Commander 请求格式
                    mcp_payload = {
                        "command": messages[-1]['content']
                    }
                elif selected_mcp == "server-sequential-thinking":
                    # Sequential Thinking 请求格式
                    mcp_payload = {
                        "prompt": messages[-1]['content'],
                        "steps": ["analyze", "plan", "execute"]
                    }
                else:
                    mcp_payload = {"query": messages[-1]['content']}

                # 发送请求到MCP服务器
                mcp_response = requests.post(
                    server_config["url"],
                    json=mcp_payload,
                    timeout=30
                )
                mcp_response.raise_for_status()
                mcp_result = mcp_response.json()

                # 根据MCP结果修改messages数组
                if mcp_result:
                    # 提取有用信息并添加到系统消息中
                    if selected_mcp == "playwright":
                        context = mcp_result.get('result', {}).get('analysis', '')
                    elif selected_mcp == "desktop-commander":
                        context = mcp_result.get('output', '')
                    elif selected_mcp == "server-sequential-thinking":
                        context = json.dumps(mcp_result.get('thinking', {}))
                    else:
                        context = json.dumps(mcp_result)

                    # 添加系统消息提供MCP上下文
                    messages.append({
                        "role": "system",
                        "content": f"Additional context from {selected_mcp} MCP: {context}"
                    })
            except Exception as e:
                print(f"MCP服务器请求失败: {e}")
                # MCP调用失败时记录错误，但继续正常调用OpenRouter
                messages.append({
                    "role": "system",
                    "content": f"Warning: Failed to get context from {selected_mcp} MCP: {str(e)}"
                })

        # 准备发送到OpenRouter的请求
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages
        }

        # 发送请求到OpenRouter
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        result = response.json()

        # 提取模型回复
        assistant_message = result['choices'][0]['message']['content']

        # 将MCP结果与LLM回复一起返回
        return jsonify({
            "reply": assistant_message,
            "mcp_data": mcp_result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # 在启动应用前初始化MCP服务器
    init_mcp_servers()
    app.run(debug=True)