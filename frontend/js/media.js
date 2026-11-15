// Can this device play a background video smoothly? Asks the browser (Media Capabilities API) whether
// it decodes the exact stream `smooth`ly and `powerEfficient`ly (in practice: in hardware). Videos are
// only an extra over the stills, so a device that would drop frames keeps the still instead of a
// stuttering film; the film itself is never made worse to fit.
export async function decodesSmoothly(nav, { type, width, height, fps, bitrate }) {
  const mc = nav && nav.mediaCapabilities;
  if (!mc || !mc.decodingInfo) return true;                 // no API (older browsers): the playback watchdog decides
  try {
    const r = await mc.decodingInfo({ type: 'file', video: { contentType: type, width, height, framerate: fps, bitrate } });
    return !!(r.supported && r.smooth && r.powerEfficient);
  } catch { return true; }
}

// Watches a playing video; calls `onBad` once if more than `share` of its frames were dropped over
// a window (decoder or compositor too slow on this machine).
export function watchDrops(v, onBad, { windowMs = 3000, share = 0.08 } = {}) {
  if (!v.getVideoPlaybackQuality) return () => {};
  let base = null, timer = 0, stopped = false;
  const tick = () => {
    if (stopped) return;
    if (!v.paused && !v.hidden) {
      const q = v.getVideoPlaybackQuality();
      if (!base) base = q;
      else {
        const total = q.totalVideoFrames - base.totalVideoFrames, dropped = q.droppedVideoFrames - base.droppedVideoFrames;
        if (total >= 60 && dropped / total > share) { stopped = true; onBad(); return; }
        if (total >= 60) base = q;                          // rolling window
      }
    } else base = null;                                      // paused time does not count
    timer = setTimeout(tick, windowMs);
  };
  timer = setTimeout(tick, windowMs);
  return () => { stopped = true; clearTimeout(timer); };
}
