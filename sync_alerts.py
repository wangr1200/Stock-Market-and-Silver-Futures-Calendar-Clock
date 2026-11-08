import os
import subprocess

def sync_to_cloud(file_name="price_alerts.json"):
    try:
        # 获取当前脚本所在目录作为仓库根目录
        repo_path = os.path.dirname(os.path.abspath(__file__))
        
        # 检查是否为 git 仓库，如果不是则自动初始化
        git_dir = os.path.join(repo_path, ".git")
        if not os.path.exists(git_dir):
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            # 设置基本身份（防止 git commit 报错）
            subprocess.run(["git", "config", "user.name", "MarketDesktopClock User"], cwd=repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "user@marketclock.local"], cwd=repo_path, check=True)
        
        # 执行 git add
        subprocess.run(["git", "add", file_name], cwd=repo_path, check=True)
        print("Git add successfully.")
    except Exception as e:
        print(f"Git sync error: {e}")
        raise e

if __name__ == "__main__":
    sync_to_cloud()
