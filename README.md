# 📈 Stock Market & Silver Futures Calendar Clock

一款专为 **A股投资者与白银期货（沪银）交易者** 精心打造的桌面浮窗市场时钟与状态监控工具。采用 Python (PyQt5) 开发，支持无边框优雅悬浮、窗口置顶、位置锁定、多开防冲突、系统托盘常驻以及一键动态休市日历查询。

---

## ✨ 核心功能特点

* **🕒 实时市场时间与倒计时**：
  * 精准显示星期、本地时间与日期。
  * 动态计算并展示 **A股**（集合竞价、上午/下午盘交易中、午休、距收盘倒计时、已收盘）。
  * 动态计算并展示 **白银期货（沪银）** 日盘与夜盘交易状态、盘中休市、集合竞价及周末/非交易时段倒计时。
* **📊 沪银主力实时行情看板**：
  * 集成板块看板，支持红绿涨跌底色自适应高亮（红涨绿跌/绿涨红跌样式），一眼掌握主力动态。
* **📅 动态休市日历面板**：
  * 内置 A 股及港股动态节假日/休市日历查询窗口（支持按月翻页、周末及法定节假日原因高亮提示，并可直达东财官方休市页面）。
* **🛠️ 桌面极简交互与配置**：
  * **无边框优雅悬浮**：支持鼠标任意拖拽摆放。
  * **位置锁定/解锁**：防止日常误触拖动窗口。
  * **全局个性化设置**：支持“窗口总在最前端”、“关闭时隐藏到托盘”以及“背景透明度自由调节（滑动条实时生效）”。
  * **开机自动启动**：一键勾选，开机即用。
  * **全局单例运行**：通过 `QSharedMemory` 严格防范多实例重复启动。

---

## 🚀 快速开始与编译部署

### 1. 环境准备
确保你的电脑已安装 Python 3.x，并安装 PyQt5 依赖：
```bash
pip install PyQt5
2. 本地运行源码
在项目根目录下执行：
python create.py
3. 使用 PyInstaller 打包为独立 .exe 程序
本项目已完美解决 PyInstaller 打包后组件透明度及样式丢失的行业痛点（采用容器 QWidget 托底架构）。如需自行打包，可运行：
pyinstaller --clean --noconsole --onefile --name="MarketClock" create.py
📂 项目结构说明
├── create.py             # 主程序源码（包含主时钟、行情面板、设置窗口与休市日历）
├── run.bat               # 快捷启动脚本
├── MarketClock.spec      # PyInstaller 编译配置文件
└── LICENSE               # 开源许可证
📜 License
本项目采用 MIT License 开源协议。
```
<img width="356" height="671" alt="image" src="https://github.com/user-attachments/assets/f24cc9b4-7c6e-4433-8a7f-7c88f5d8a674" />
<img width="376" height="444" alt="image" src="https://github.com/user-attachments/assets/69ac5659-11a3-4bd3-8e07-8d33acc0c6d9" />
<img width="483" height="354" alt="image" src="https://github.com/user-attachments/assets/9bfa726a-83fa-4f34-9a00-0712bfc48d8d" />
<img width="364" height="405" alt="image" src="https://github.com/user-attachments/assets/f81e30da-df50-4e19-9adf-ed1de9357dfb" />
<img width="436" height="547" alt="image" src="https://github.com/user-attachments/assets/25b2a7f6-67df-42ba-ac3f-fceb7f4220a3" />

