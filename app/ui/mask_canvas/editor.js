/* Standalone Streamlit v1 message protocol. No remote scripts or requests. */
"use strict";
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const status = document.getElementById("status");
const mode = document.getElementById("mode");
const radius = document.getElementById("radius");
const overlay = document.getElementById("overlay");
const undo = document.getElementById("undo");
const reset = document.getElementById("reset");
let args = null, bits = [], history = [], photo = null, pointer = null, previous = null;
let disabled = false, lastSent = null;
const maskCanvas = document.createElement("canvas");
const maskCtx = maskCanvas.getContext("2d");
function send(type, payload) {
  window.parent.postMessage({isStreamlitMessage: true, type, ...payload}, "*");
}
function frameHeight() {
  send("streamlit:setFrameHeight", {height: document.body.scrollHeight + 4});
}
function draw() {
  if (!args || !photo) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(photo, 0, 0, canvas.width, canvas.height);
  if (overlay.checked) {
    const pixels = maskCtx.createImageData(args.width, args.height);
    bits.forEach((bit, i) => {
      pixels.data[i * 4] = 0; pixels.data[i * 4 + 1] = 210;
      pixels.data[i * 4 + 2] = 120; pixels.data[i * 4 + 3] = bit === "1" ? 100 : 0;
    });
    maskCtx.putImageData(pixels, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(maskCanvas, 0, 0, canvas.width, canvas.height);
  }
  undo.disabled = disabled || !history.length;
  reset.disabled = disabled;
  frameHeight();
}
function remember() {
  history.push(bits.join(""));
  if (history.length > 20) history.shift();
}
function commit(useOriginal = false) {
  const pixels = bits.join("");
  lastSent = pixels;
  send("streamlit:setComponentValue", {dataType: "json", value: {
    image_token: args.image_token, width: args.width, height: args.height, pixels, use_original: useOriginal
  }});
  status.textContent = useOriginal ? "已恢复自动分割。" : "已提交修正，下方预览将同步更新。";
  draw();
}
function position(event) {
  const rect = canvas.getBoundingClientRect();
  return [Math.max(0, Math.min(args.width, (event.clientX - rect.left) / rect.width * args.width)),
          Math.max(0, Math.min(args.height, (event.clientY - rect.top) / rect.height * args.height))];
}
function dab(x, y) {
  const r = Number(radius.value);
  for (let yy = Math.max(0, Math.floor(y - r)); yy < Math.min(args.height, Math.ceil(y + r)); yy++) {
    for (let xx = Math.max(0, Math.floor(x - r)); xx < Math.min(args.width, Math.ceil(x + r)); xx++) {
      if ((xx + 0.5 - x) ** 2 + (yy + 0.5 - y) ** 2 <= r ** 2) bits[yy * args.width + xx] = mode.value;
    }
  }
}
canvas.addEventListener("pointerdown", event => {
  if (!args || !photo || disabled || pointer !== null || event.button !== 0) return;
  event.preventDefault(); remember(); pointer = event.pointerId;
  canvas.setPointerCapture(pointer); previous = position(event); dab(...previous); draw();
  status.textContent = "正在修正，松开后生效…";
});
canvas.addEventListener("pointermove", event => {
  if (pointer !== event.pointerId) return;
  const next = position(event);
  const steps = Math.max(1, Math.ceil(Math.hypot(next[0] - previous[0], next[1] - previous[1]) * 2));
  for (let i = 1; i <= steps; i++) dab(previous[0] + (next[0] - previous[0]) * i / steps,
                                    previous[1] + (next[1] - previous[1]) * i / steps);
  previous = next; draw();
});
function finish(event) {
  if (pointer !== event.pointerId) return;
  pointer = null; previous = null; commit();
}
canvas.addEventListener("pointerup", finish);
canvas.addEventListener("pointercancel", finish);
canvas.addEventListener("lostpointercapture", finish);
undo.addEventListener("click", () => {
  if (disabled || !history.length || pointer !== null) return;
  bits = history.pop().split(""); commit(bits.join("") === args.base_pixels);
});
reset.addEventListener("click", () => {
  if (disabled || !args || pointer !== null) return;
  remember(); bits = args.base_pixels.split(""); commit(true);
});
overlay.addEventListener("change", draw);
window.addEventListener("message", event => {
  if (event.source !== window.parent || event.data?.type !== "streamlit:render") return;
  const next = event.data.args;
  disabled = Boolean(event.data.disabled);
  if (!next || !Number.isInteger(next.width) || !Number.isInteger(next.height)
      || next.width < 1 || next.height < 1 || next.width > 160 || next.height > 160
      || !/^[01]+$/.test(next.current_pixels) || next.current_pixels.length !== next.width * next.height) return;
  const changed = !args || args.image_token !== next.image_token;
  args = next;
  if (changed) {
    bits = args.current_pixels.split(""); history = []; pointer = null; lastSent = null;
    maskCanvas.width = args.width; maskCanvas.height = args.height;
    canvas.width = Math.round(600 * args.width / Math.max(args.width, args.height));
    canvas.height = Math.round(600 * args.height / Math.max(args.width, args.height));
    const loading = new Image(); const token = args.image_token;
    loading.onload = () => {
      if (args.image_token !== token) return;
      photo = loading; status.textContent = "拖动笔刷修正绿色选区，每笔松开后生效。"; draw();
    };
    loading.onerror = () => { status.textContent = "照片载入失败，请重新打开主体修正。"; frameHeight(); };
    photo = null; loading.src = args.image_url;
  } else if (pointer === null && args.current_pixels === lastSent) {
    // Server acknowledgement. Never overwrite a newer local stroke with a
    // stale argument from the rerun that first received the preceding value.
    status.textContent = "修正已同步。";
  }
  draw(); frameHeight();
});
new ResizeObserver(frameHeight).observe(document.body);
send("streamlit:componentReady", {apiVersion: 1});
frameHeight();
