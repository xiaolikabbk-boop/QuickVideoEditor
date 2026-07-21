import random
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from music_batcher import ExportJob, MediaInfo, OverlaySpec, add_white_outline, assign_music, assign_overlays, build_ffmpeg_command, output_path_for


class MusicBatcherTests(unittest.TestCase):
    def test_assigns_without_repeats_until_pool_is_exhausted(self):
        videos = [Path(f"v{i}.mp4") for i in range(7)]
        music = [Path(f"m{i}.mp3") for i in range(3)]
        result = [song for _, song in assign_music(videos, music, random.Random(3))]
        self.assertEqual(3, len(set(result[:3])))
        self.assertEqual(3, len(set(result[3:6])))
        self.assertNotEqual(result[2], result[3])

    def test_command_copies_video_and_mixes_audio(self):
        job = ExportJob(Path("in.mp4"), Path("song.mp3"), Path("out.mp4"))
        command = build_ffmpeg_command(job, MediaInfo(18.25, True), 0.7, 0.25, ffmpeg="ffmpeg")
        joined = " ".join(command)
        self.assertIn("-c:v copy", joined)
        self.assertIn("amix=inputs=2", joined)
        self.assertIn("afade=t=out:st=17.250000:d=1.000000", joined)
        self.assertIn("-stream_loop -1", joined)

    def test_command_supports_silent_video(self):
        job = ExportJob(Path("in.mp4"), Path("song.mp3"), Path("out.mp4"))
        command = build_ffmpeg_command(job, MediaInfo(0.4, False), 0.7, 0.25, ffmpeg="ffmpeg")
        joined = " ".join(command)
        self.assertNotIn("[0:a:0]", joined)
        self.assertIn("afade=t=out:st=0.000000:d=0.400000", joined)

    def test_command_overlays_optional_transparent_image(self):
        overlays = (OverlaySpec(Path("image.png"), "right", 0.5),)
        job = ExportJob(Path("in.mp4"), Path("song.mp3"), Path("out.mp4"), overlays)
        command = build_ffmpeg_command(job, MediaInfo(12, True, 1080, 1920), 0.7, 0.25, ffmpeg="ffmpeg")
        joined = " ".join(command)
        self.assertIn("-loop 1 -i image.png", joined)
        self.assertIn("scale=w=540:h=922", joined)
        self.assertIn("overlay=x=main_w-overlay_w-main_w*0.02:y=main_h-overlay_h", joined)
        self.assertIn("-c:v libx264", joined)

    def test_random_overlay_layout_uses_one_or_two_bottom_sides(self):
        videos = [Path(f"v{i}.mp4") for i in range(10)]
        images = [Path(f"i{i}.png") for i in range(5)]
        result = assign_overlays(videos, images, random.Random(7))
        self.assertTrue(all(len(overlays) in (1, 2) for _, overlays in result))
        self.assertTrue(all(overlay.side in ("left", "right") for _, overlays in result for overlay in overlays))
        for _, overlays in result:
            if len(overlays) == 2:
                self.assertEqual({"left", "right"}, {overlay.side for overlay in overlays})

    def test_command_keeps_video_copy_without_image(self):
        job = ExportJob(Path("in.mp4"), Path("song.mp3"), Path("out.mp4"))
        command = build_ffmpeg_command(job, MediaInfo(12, True), 0.7, 0.25, ffmpeg="ffmpeg")
        self.assertIn("copy", command)

    def test_adds_white_outline_around_alpha_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            output = Path(folder) / "outlined.png"
            image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((12, 12, 27, 27), fill=(200, 20, 20, 255))
            image.save(source)
            add_white_outline(source, output, 40, 40, 4)
            with Image.open(output) as outlined:
                self.assertEqual((48, 48), outlined.size)
                self.assertEqual((255, 255, 255, 255), outlined.getpixel((12, 24)))
                self.assertEqual((200, 20, 20, 255), outlined.getpixel((20, 20)))

    def test_output_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "clip.mov"
            output_folder = Path(folder) / "已配乐"
            output_folder.mkdir()
            (output_folder / "clip_配乐.mp4").touch()
            self.assertEqual("clip_配乐_2.mp4", output_path_for(video).name)


if __name__ == "__main__":
    unittest.main()
