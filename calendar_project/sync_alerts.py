# -*- coding: utf-8 -*-
"""
sync_alerts.py - MarketDesktopClock 云端同步与预警推送辅助脚本
支持多线程异步执行 Git 同步（add, commit, push）与 Server酱微信推送，避免网络卡顿导致 UI 线程阻塞。
"""

import os
import json
import subprocess
import requests
from PyQt5.QtCore import QThread, pyqtSignal

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".market_clock_cache")

def get_server_key():
    """统一安全获取 Server酱 Key: 优先环境变量，其次 config.json"""
    key = os.getenv("SERVER_CHAN_KEY") or os.getenv("SCKEY")
    if key:
        return key.strip()
    try:
        config_file = os.path.join(CACHE_DIR, "config.json")
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (data.get("server_chan_key", "") or data.get("server_key", "")).strip()
    except Exception:
        pass
    return ""


class GitSyncWorker(QThread):
    """后台异步执行 Git 同步与 Server酱推送的线程类"""
    finished_signal = pyqtSignal(bool, str)  # 成功状态 (bool), 提示信息 (str)

    def __init__(self, repo_path=None, commit_msg="Auto-sync: update alert configs"):
        super().__init__()
        if repo_path:
            self.repo_path = repo_path
        else:
            self.repo_path = os.path.dirname(os.path.abspath(__file__))
        self.commit_msg = commit_msg

    def run(self):
        try:
            git_dir = os.path.join(self.repo_path, ".git")
            if not os.path.isdir(git_dir):
                self.finished_signal.emit(False, "错误: 未找到 .git 目录，无法进行 Git 同步")
                return

            res_add = subprocess.run(
                ["git", "add", "."],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if res_add.returncode != 0:
                self.finished_signal.emit(False, f"Git add 失败: {res_add.stderr.strip()}")
                return

            res_commit = subprocess.run(
                ["git", "commit", "-m", self.commit_msg],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if res_commit.returncode != 0:
                stdout_lower = res_commit.stdout.lower()
                if "nothing to commit" not in stdout_lower and "nothing added to commit" not in stdout_lower:
                    pass

            res_push = subprocess.run(
                ["git", "push"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            if res_push.returncode != 0:
                err_msg = res_push.stderr.strip() or res_push.stdout.strip()
                self.finished_signal.emit(False, f"Git push 失败 (网络或VPN较慢): {err_msg}")
                return

            self.finished_signal.emit(True, "云端同步成功 (Git Push 完成)")

        except subprocess.TimeoutExpired:
            self.finished_signal.emit(False, "Git 同步超时：网络连接较慢或 VPN 响应延迟，请检查网络状态")
        except Exception as e:
            self.finished_signal.emit(False, f"同步异常错误: {str(e)}")


def sync_to_cloud(repo_path=None, commit_msg="Auto-sync: update alert configs"):
    path = repo_path or os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(["git", "add", "."], cwd=path, check=True, timeout=10)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=path, timeout=10)
        subprocess.run(["git", "push"], cwd=path, check=True, timeout=30)
        return True, "同步成功"
    except subprocess.TimeoutExpired:
        return False, "同步超时"
    except subprocess.CalledProcessError as e:
        return False, f"同步失败: {str(e)}"
    except Exception as e:
        return False, f"异常: {str(e)}"


def send_serverchan_notification(title, desp="", sckey=None):
    """
    Server酱微信推送通知辅助函数（已修复：支持自动从 config.json 及环境变量读取 Key）
    """
    key = sckey or get_server_key()
    if not key:
        return False, "未配置 Server酱 SCKEY"
    
    url = f"https://sctapi.ftqq.com/{key}.send"
    data = {
        "title": title,
        "desp": desp
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("code") == 0:
                return True, "微信推送成功"
            else:
                return False, f"Server酱返回错误: {res_json.get('message')}"
        return False, f"HTTP 请求失败: {response.status_code}"
    except Exception as e:
        return False, f"推送异常: {str(e)}"