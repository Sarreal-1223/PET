# 小三花桌面宠物

一个使用 Python 3.11/3.12、uv 和 PySide6 编写的 Windows 桌面宠物。窗口透明、无边框并保持置顶；小猫可以拖动，左键抚摸，右键打开中文菜单。

## 启动

先安装 [uv](https://docs.astral.sh/uv/)，然后在项目目录运行：

```powershell
uv run --python 3.12 calico-pet
```

首次启动时，uv 会准备 Python 3.12 并安装项目依赖。也可以使用 `uv run --python 3.12 python -m calico_pet` 启动。

## 交互

- 左键单击小猫：抚摸并提升心情、亲密度。
- 按住左键拖动：移动小猫在桌面上的位置。
- 右键：喂食、玩耍、睡觉/叫醒、查看状态、修改名字或退出。
- 饱食度、心情、精力和亲密度均限制在 0–100；状态会随时间变化并在退出/定时保存。
- 重启会读取上次状态并补算离线期间的变化。

## 文件与状态

- `assets/calico_spritesheet.png`：透明三花猫精灵图；全部非空格都被切帧使用，包含待机、左右走动、挥爪、蹦跳、眨眼、歪头、独立踩奶、闭眼睡觉及多方向张望。
- `assets/calico_pose_sheet.png`：neutral 姿态加全身与近景两组 16 方向转头帧；浅灰底会在切帧时移除，neutral 姿态加入 idle 循环。
- idle、walk、睡觉和各类动作均由 `QTimer` 逐帧驱动；睡觉使用闭眼循环，踩奶是独立可选动作。玩耍时先以更明显的自然上下弧线蹦跳，再原地走动；抬头/低头方向已按画面修正。拖动小猫时按方向显示走动帧。右键“动作展示”可触发图集动作和两组转头序列。
- 如果图片不存在或无法读取，程序会改用 Qt 绘制的三花猫占位图。
- 宠物状态和窗口位置保存在当前 Windows 用户的应用数据目录 `CalicoPet/pet_state.json`，不会写入项目目录。

## 开发验证

```powershell
uv run --python 3.12 python -m compileall src
uv run --python 3.12 python -m unittest discover -s tests
```

此应用是桌面 GUI 程序，启动后可从小猫右键菜单退出。

