# -*- coding: utf-8 -*-
"""
sync_alerts.py - MarketDesktopClock 云端同步与预警推送辅助脚本
支持多线程异步执行 Git 同步（add, commit, push）与 Server酱微信推送，避免网络卡顿导致 UI 线程阻塞。
"""

import os
import subprocess
import requests
from PyQt5.QtCore import QThread, pyqtSignal

class GitSyncWorker(QThread):
    """后台异步执行 Git 同步与 Server酱推送的线程类"""
    finished_signal = pyqtSignal(bool, str)  # 成功状态 (bool), 提示信息 (str)

    def __init__(self, repo_path=None, commit_msg="Auto-sync: update alert configs"):
        super().__init__()
        # 默认定位到脚本所在同级目录（项目根目录，与 .git 同级）
        if repo_path:
            self.repo_path = repo_path
        else:
            self.repo_path = os.path.dirname(os.path.abspath(__file__))
        self.commit_msg = commit_msg

    def run(self):
        try:
            # 1. 检查是否存在 .git 目录
            git_dir = os.path.join(self.repo_path, ".git")
            if not os.path.isdir(git_dir):
                self.finished_signal.emit(False, "错误: 未找到 .git 目录，无法进行 Git 同步")
                return

            # 2. 执行 git add .
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

            # 3. 执行 git commit
            res_commit = subprocess.run(
                ["git", "commit", "-m", self.commit_msg],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            # 如果没有变动（nothing to commit），commit 返回码非 0 属于正常情况，可继续或提示
            # 这里对常见无变动提示做兼容
            if res_commit.returncode != 0:
                stdout_lower = res_commit.stdout.lower()
                if "nothing to commit" not in stdout_lower and "nothing added to commit" not in stdout_lower:
                    # 如果不是因为没有修改导致的，则可能是其他配置错误
                    pass

            # 4. 执行 git push (最容易因网络/VPN慢而阻塞的环节，设置合理的 timeout=30秒)
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
    """
    阻塞式同步函数（适用于非 UI 场景或命令行调用）。
    如果在 PyQt GUI 中调用，建议使用上方的 GitSyncWorker 异步线程，以防 UI 卡死。
    """
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
    Server酱微信推送通知辅助函数
    """
    key = sckey or os.environ.get("SCKEY")
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
