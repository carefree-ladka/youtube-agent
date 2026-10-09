import {Config} from "@remotion/cli/config";

// H.264 MP4 output, suitable for YouTube Shorts / Reels and long-form.
Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");
Config.setConcurrency(2);
// Allow loading staticFile() assets (audio, images, sfx) from the public dir.
Config.setChromiumOpenGlRenderer("angle");
