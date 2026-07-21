# 批量配乐工具

把多条视频拖入窗口，程序会从指定音乐文件夹中优先不重复地随机配乐，并批量输出成品。

当前版本：`v1.0.0`

日常使用可直接打开 `dist/批量配乐工具/批量配乐工具.exe`。

- 保留原视频画质、分辨率和帧率
- 原声和背景音乐音量可调
- 可选透明图片文件夹，批量随机叠加 PNG/WebP 图片
- 每条视频随机使用 1～2 张透明图，在左下/右下位置随机选择尺寸
- 可选为每张透明图自动生成白色描边
- 长音乐自动裁短，短音乐自动循环
- 背景音乐在结尾 1 秒淡出
- 输出到原视频旁的 `已配乐` 文件夹，不覆盖已有文件
- 启动后后台检查 GitHub Releases，也可在程序内手动“检查更新”
- 更新包使用 SHA-256 校验，独立更新助手整体替换目录，失败自动回滚

开发运行：

```powershell
python -m pip install -r requirements.txt
python app.py
```

测试：

```powershell
python -m unittest -v
```

## 构建 Windows 发布包

机器需要 Python 3.13，并确保 `ffmpeg.exe` 和 `ffprobe.exe` 位于同一个 PATH 目录：

```powershell
python -m pip install -r requirements.txt
.\scripts\build_release.ps1 -Version 1.0.0
```

脚本将生成：

- `release/QuickVideoEditor-v1.0.0-win-x64.zip`
- `release/QuickVideoEditor-v1.0.0-win-x64.zip.sha256`
- `release/QuickVideoEditor-v1.0.0-Setup.exe`
- `release/QuickVideoEditor-v1.0.0-Setup.exe.sha256`

`Setup.exe` 用于新电脑首次安装，默认安装到当前用户的 `%LOCALAPPDATA%\Programs\QuickVideoEditor`，不需要管理员权限。zip 内含完整的 `批量配乐工具` onedir 目录以及独立的 `更新助手.exe`，用于程序内更新。不要只发布主 exe。

## 首次发布

1. 确认 `version.py` 的 `APP_VERSION` 与目标版本一致。
2. 执行测试与构建脚本。
3. 在 GitHub 仓库进入 `Releases`，选择 `Draft a new release`。
4. 新建标签 `v1.0.0`，填写中文版本说明。
5. 上传安装器、zip 和各自同名的 `.sha256`，然后发布 Release。

也可以提交代码后创建并推送 `v1.0.0` 标签，由 GitHub Actions 自动测试、构建和创建 Release。

## 后续升级

1. 按语义版本更新 `APP_VERSION`，例如修复版从 `1.0.0` 升到 `1.0.1`。
2. 完成代码修改并运行 `python -m unittest -v`。
3. 执行 `.\scripts\build_release.ps1 -Version 1.0.1`。
4. 创建标签 `v1.0.1` 和对应 GitHub Release，上传两个同名资产。

程序只接受严格匹配当前版本号的资产名称。GitHub 或网络不可用时，自动检查会静默结束，不影响视频处理。
