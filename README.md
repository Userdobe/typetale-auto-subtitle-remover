# 字字动画｜自动去字幕插件

## 作用

它监视字字动画的**视频输出目录**。检测到新生成的 MP4/MOV/MKV/WEBM 后，自动生成同目录的 `原文件名_no_subtitles.mp4`：

- 原视频不覆盖，便于回退；
- 尝试保留原音频；
- 对底部字幕的文字区域做 OpenCV 内容修复；
- 无需云端 API，不上传视频。

> 重要：字字动画官方公开仓库说明了 Python 插件能力，但没有公开稳定的“导出完成后处理”Hook。这个版本因此采用旁路监视器，不修改字字动画主程序，也不冒充官方原生插件。若你的版本在 `_internal/plugins` 中有额外插件 API，可再改成原生软件级插件。

## 安装（Windows）

1. 安装 **Python 3.10 或更高版本**，安装时勾选 `Add Python to PATH`。
2. 安装 **FFmpeg**，并把包含 `ffmpeg.exe` 的 `bin` 目录加入系统 PATH。
3. 将整个本目录复制到任意位置，例如：`D:\TypeTale\plugins\auto_remove_subtitles`。
4. 复制 `config.example.json` 为 `config.json`，修改 `watch_dir` 为字字动画实际的视频输出目录，例如：

```json
{
  "watch_dir": "D:/TypeTale/outputs"
}
```

5. 双击 `start_watcher.bat`，保持窗口运行；之后字字动画每输出一个视频，插件就会自动处理。
6. 想退出时，在黑色窗口按 `Ctrl+C`。

## 配置

- `bottom_ratio`：检测底部区域的高度比例，默认 `0.28`；字幕更高时改为 `0.35`。
- `mask_padding`：字幕周围扩展像素，默认 `10`；残留描边时可改为 `16`。
- `inpaint_method`：`telea` 速度快，`ns` 对较大区域有时更自然。
- `keep_audio`：保持 `true`。
- `overwrite`：保持 `false`，不要覆盖原视频。

## 单个视频测试

```bat
python remove_subtitles.py --config config.json --input "D:\视频\test.mp4"
```

## 安装到字字动画插件目录（可选）

如果你的字字动画安装目录中存在 `_internal\plugins`，可以把本文件夹复制进去作为工具插件目录；但本插件的自动监视仍需双击 `start_watcher.bat`。请不要替换或删除 `_internal` 内原有文件。

## 限制

- 适合**固定在画面底部**的硬字幕；字幕压在人物脸上、滚动字幕、复杂背景上的字幕，修复质量会下降。
- 该版本不会删除可关闭的字幕轨道；可关闭字幕应在字字动画导出设置中关闭字幕。
- 首次处理需要 OpenCV 解码/编码，耗时取决于视频长度和分辨率。
- 处理结果请人工抽查，尤其是复杂运动背景。
