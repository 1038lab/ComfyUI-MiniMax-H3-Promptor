import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const NODE = "H3_Vision_Analyzer";
const WIDTH = 440;
const INITIAL_NODE_HEIGHT = 400;

// CSS Styles
const style = document.createElement("style");
style.textContent = `
    .mmv-box { border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 5px; margin: 0 0 6px; background: rgba(0, 0, 0, 0.15); box-sizing: border-box; width: 100%; }
    .mmv-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; width: 100%; }
    .mmv-drop { aspect-ratio: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #08b4ed; cursor: pointer; border: 1px dashed rgba(255,255,255,0.15); border-radius: 6px; background: rgba(0, 0, 0, 0.4); padding: 4px; box-sizing: border-box; transition: background 0.2s, border-color 0.2s; }
    .mmv-drop:hover { border-color: #0aa4d6; background: rgba(0, 0, 0, 0.25); }
    .mmv-reference-empty { grid-column: 1 / -1; width: 100%; aspect-ratio: 5/1; align-items: center; justify-content: center; text-align: left; padding: 18px 24px; flex-direction: row; gap: 10px; }
    .mmv-drop-icon { font-size: 14px; margin: 0; color: #08b4ed; font-family: Arial, sans-serif; }
    .mmv-drop-title { font-size: 11px; color: #d9e8f2; }
    .mmv-card { min-width: 0; aspect-ratio: 1; border: 1px solid #30485c; border-radius: 6px; background: #1a2938; overflow: hidden; position: relative; cursor: pointer; }
    .mmv-card img, .mmv-card video { display: block; width: 100%; height: 100%; object-fit: contain; background: #071018; }
    .mmv-card:hover { border-color: #0aa4d6; box-shadow: 0 0 0 1px #0aa4d6; }
    .mmv-card-name { position: absolute; left: 0; right: 0; bottom: 0; padding: 2px 15px 2px 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #fff; background: rgba(10,20,30,.6); font-size: 8px; line-height: 1.15; }
    .mmv-remove { position: absolute; right: 1px; top: 1px; border: 0; background: rgba(0,0,0,0.5); color: #fff; cursor: pointer; font-size: 12px; z-index: 3; border-radius: 50%; width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; padding: 0;}
    .mmv-remove:hover { background: #d47d8b; }
    .mmv-status-bar { grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; padding: 3px 6px; min-height: 18px; background: rgba(0,0,0,0.25); border-radius: 4px; margin-top: 4px; margin-bottom: 2px; }
    .mmv-limit-msg { font-size: 10px; color: #d47d8b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .mmv-clear-all { display: inline-flex; align-items: center; gap: 4px; font-size: 9px; color: #a44; cursor: pointer; padding: 2px 6px; border: 1px solid #844; border-radius: 4px; background: rgba(100,0,0,0.2); }
    .mmv-clear-all:hover { background: rgba(255,0,0,0.3); color: #f66; border-color: #f66; }
    .mmv-prompt { flex: 1; display: block; width: 100%; min-height: 80px; resize: none; overflow: auto; box-sizing: border-box; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; background: rgba(0, 0, 0, 0.35); color: var(--input-text, #e1e9ef); padding: 5px; font: 12px/1.4 Arial, sans-serif; outline: none; user-select: text; scrollbar-width: thin; scrollbar-color: #1f3540 transparent; }
    .mmv-prompt::placeholder { color: #6f7d89; opacity: 1; }
    .mmv-media-controls { position: absolute; left: 3px; right: 3px; bottom: 12px; z-index: 4; height: 14px; display: flex; align-items: center; color: rgba(255,255,255,.6); font: 8px/1 Arial, sans-serif; pointer-events: none; }
    .mmv-media-toggle { width: 14px; height: 14px; padding: 0; border: 0; background: rgba(0,0,0,.65); border-radius: 50%; cursor: pointer; opacity: .6; display: flex; align-items: center; justify-content: center; pointer-events: auto; }
    .mmv-media-toggle svg { display: block; width: 10px; height: 10px; }
`;
document.head.appendChild(style);

function make(tag, css = {}, text = "") {
    const el = document.createElement(tag);
    Object.assign(el.style, css);
    if (text) el.textContent = text;
    return el;
}

function kindOf(file) {
    if (file.type?.startsWith("image/") || /\\.?(png|jpe?g|webp|bmp|gif)$/i.test(file.name)) return "image";
    if (file.type?.startsWith("video/") || /\\.?(mp4|mov|webm|mkv|avi)$/i.test(file.name)) return "video";
    if (file.type?.startsWith("audio/") || /\\.?(mp3|wav|flac|m4a|ogg|aac)$/i.test(file.name)) return "audio";
    return null;
}

function fileUrl(name) {
    if (!name) return "";
    const parts = String(name).replaceAll("\\\\", "/").split("/").filter(Boolean);
    const filename = parts.pop() || "";
    const params = new URLSearchParams({ filename, type: "input", subfolder: parts.join("/") });
    return `/view?${params.toString()}`;
}

async function uploadFile(file) {
    const body = new FormData();
    body.append("image", file, file.name);
    body.append("type", "input");
    const response = await api.fetchApi("/upload/image", { method: "POST", body });
    if (!response.ok) throw new Error(`Upload failed: ${response.status}`);
    const result = await response.json();
    return [result.subfolder, result.name].filter(Boolean).join("/");
}

function hideWidget(w) {
    if (!w) return;
    w.hidden = true;
    w.options = w.options || {};
    w.options.hidden = true;
    w.computeSize = () => [0, -4];
    w.serialize = true;
}

function widget(node, name) {
    return node.widgets?.find(w => w.name === name);
}

function createPanel(node) {
    if (typeof node.addDOMWidget !== "function") return false;

    // Hide standard widgets we are replacing with our DOM panel
    hideWidget(widget(node, "_media_state"));
    hideWidget(widget(node, "custom_prompt_override"));

    const root = make("div", {
        position: "relative",
        width: `100%`,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        boxSizing: "border-box",
        color: "#d7e3ef",
        fontFamily: "Arial,sans-serif",
        fontSize: "12px",
        userSelect: "none",
        padding: "3px 4px 6px 4px",
        overflow: "visible"
    });

    const syncNodeHeight = () => {
        if (!node.size) return;
        const required = node.computeSize([node.size[0], node.size[1]]);
        if (node.size[1] < required[1]) {
            node.setSize([node.size[0], required[1]]);
            node.setDirtyCanvas?.(true, true);
        }
    };

    const media = new Map();
    let slotCounter = 0;
    let uploadNotice = "";
    let noticeTimeout = null;

    const setUploadNotice = (msg, timeout = 0) => {
        uploadNotice = msg;
        clearTimeout(noticeTimeout);
        let msgNode = root.querySelector(".mmv-limit-msg");
        if (msgNode) {
            msgNode.textContent = msg || "\u00A0";
        }
        if (timeout > 0) {
            noticeTimeout = setTimeout(() => { setUploadNotice(""); }, timeout);
        }
        requestAnimationFrame(syncNodeHeight);
    };

    // Attempt to load saved state
    const stateWidget = widget(node, "_media_state");
    if (stateWidget && stateWidget.value) {
        try {
            const data = JSON.parse(stateWidget.value);
            if (data.media) {
                data.media.forEach(entry => {
                    media.set(entry[0], entry[1]);
                    // Update slotCounter reliably
                    const num = parseInt(entry[0].replace("slot_", ""));
                    if (!isNaN(num) && num > slotCounter) slotCounter = num;
                });
            }
        } catch (e) {
            console.error("Failed to parse _media_state", e);
        }
    }

    const overrideWidget = widget(node, "custom_prompt_override");
    let layoutLock = false;

    const persistState = () => {
        const stateStr = JSON.stringify({
            media: [...media.entries()]
        });
        if (stateWidget) {
            stateWidget.value = stateStr;
            stateWidget.callback?.call(stateWidget, stateStr);
        }
    };

    function getOrdinal(slot, kind) {
        const list = [...media.entries()].filter(([s, e]) => e.kind === kind).sort((a, b) => a[0].localeCompare(b[0]));
        return list.findIndex(([s]) => s === slot) + 1;
    }

    function insertTagIntoOverride(tagStr) {
        const textarea = promptTextarea;
        if (!textarea) return;

        let val = textarea.value;

        if (val.includes(tagStr.trim())) {
            return; // Prevent inserting duplicate tags
        }

        const prefix = val && !val.endsWith("\n") ? "\n" : "";
        const combined = (val + prefix + tagStr).trimEnd();

        const lines = combined.split("\n");
        const otherLines = [];
        const taggedLines = [];

        lines.forEach(line => {
            const m = line.match(/^<\s*(Picture|Video|Audio|Video Audio)\s+(\d+)\s*>:/i);
            if (m) {
                const type = m[1].toLowerCase(), num = parseInt(m[2], 10);
                const w = type.includes("picture") ? 1000 : type === "video" ? 2000 : 3000;
                taggedLines.push({ line, weight: w + num });
            } else {
                otherLines.push(line);
            }
        });

        taggedLines.sort((a, b) => a.weight - b.weight);
        textarea.value = [...otherLines, ...taggedLines.map(t => t.line)].join("\n");

        textarea.focus();
        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;

        if (overrideWidget) {
            overrideWidget.value = textarea.value;
            overrideWidget.callback?.call(overrideWidget, textarea.value);
        }
    }

    function card(slot, entry) {
        const item = make("div");
        item.className = "mmv-card";

        if (entry.kind === "image") {
            const img = make("img");
            img.src = fileUrl(entry.name);
            item.appendChild(img);
        } else if (entry.kind === "video") {
            const video = make("video");
            video.src = fileUrl(entry.name);
            video.muted = true;
            video.preload = "metadata";
            item.appendChild(video);

            const controls = make("div"); controls.className = "mmv-media-controls";
            const toggle = make("button"); toggle.className = "mmv-media-toggle";
            toggle.innerHTML = '<svg viewBox="0 0 12 12"><path d="M2.5 1.5 10 6l-7.5 4.5Z" fill="rgba(255,255,255,.6)" stroke="rgba(255,255,255,.6)" stroke-width="1"/></svg>';

            let isPlaying = false;
            toggle.onclick = e => {
                e.stopPropagation();
                if (video.paused) { video.play(); isPlaying = true; toggle.innerHTML = '<svg viewBox="0 0 12 12"><path d="M3 2v8M9 2v8" fill="none" stroke="rgba(255,255,255,.6)" stroke-width="1.5"/></svg>'; }
                else { video.pause(); isPlaying = false; toggle.innerHTML = '<svg viewBox="0 0 12 12"><path d="M2.5 1.5 10 6l-7.5 4.5Z" fill="rgba(255,255,255,.6)" stroke="rgba(255,255,255,.6)" stroke-width="1"/></svg>'; }
            };
            controls.appendChild(toggle);
            item.appendChild(controls);
        } else if (entry.kind === "audio") {
            item.appendChild(make("div", { height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#8ea3b4", fontSize: "22px" }, "♫"));
        }

        const ordinal = getOrdinal(slot, entry.kind);
        const typeLabel = entry.kind === "image" ? "picture" : entry.kind === "video" ? "video" : "audio";
        item.appendChild(make("div", {}, `${typeLabel} ${ordinal}`)).className = "mmv-card-name";

        item.onpointerenter = () => setUploadNotice(`[${typeLabel} ${ordinal}] ${entry.name.split("/").pop()}`);
        item.onpointerleave = () => setUploadNotice("");

        const remove = make("button", {}, "×");
        remove.className = "mmv-remove";
        remove.title = "Delete media";
        remove.onclick = e => {
            e.stopPropagation();
            media.delete(slot);
            persistState();
            render();
        };
        item.appendChild(remove);

        item.onclick = e => {
            if (e.target.closest("button")) return;
            e.stopPropagation();
            const ordinal = getOrdinal(slot, entry.kind);
            const label = entry.kind === "image" ? "Picture" : entry.kind === "video" ? "Video" : "Audio";
            insertTagIntoOverride(`<${label} ${ordinal}>: `);
        };

        if (entry.kind === "video") {
            item.ondblclick = e => {
                if (e.target.closest("button")) return;
                e.stopPropagation();
                const ordinal = getOrdinal(slot, entry.kind);
                insertTagIntoOverride(`<Video Audio ${ordinal}>: `);
            };
        }

        return item;
    }

    function addDrop(isEmpty = false) {
        const d = make("div");
        d.className = isEmpty ? "mmv-drop mmv-reference-empty" : "mmv-drop";

        if (isEmpty) {
            const title = make("div");
            title.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;gap:6px;font-size:14px;font-weight:600;color:#fff;margin-bottom:6px;font-family:system-ui,sans-serif;letter-spacing:0.5px;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0aa4d6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>Drag & Drop</div><div style="font-size:11px;color:#8ea3b4;text-align:center;font-family:system-ui,sans-serif;opacity:0.8;">or click to upload your media files</div>';
            d.append(title);
        } else {
            const icon = make("span");
            icon.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:block;margin:0 auto 4px auto;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>';
            icon.className = "mmv-drop-icon";
            const title = make("span", {}, "+ Add");
            title.className = "mmv-drop-title";
            d.append(icon, title);
        }

        d.onclick = () => {
            const input = document.createElement("input");
            input.type = "file";
            input.multiple = true;
            input.accept = "image/*,video/*,audio/*";
            input.onchange = () => accept(input.files);
            input.click();
        };

        d.ondragover = e => { e.preventDefault(); e.stopPropagation(); d.style.borderColor = "#0aa4d6"; };
        d.ondragleave = e => { e.preventDefault(); e.stopPropagation(); d.style.borderColor = ""; };
        d.ondrop = e => { e.preventDefault(); e.stopPropagation(); accept(e.dataTransfer.files); };
        return d;
    }

    async function accept(files) {
        setUploadNotice("");
        for (const file of files || []) {
            const kind = kindOf(file);
            if (!kind) continue;

            const currentCount = [...media.values()].filter(e => e.kind === kind).length;
            const maxLimit = kind === "image" ? 9 : (kind === "video" ? 3 : 3);
            if (currentCount >= maxLimit) {
                setUploadNotice(`Up to ${maxLimit} ${kind}s allowed.`, 30000);
                continue;
            }

            try {
                document.body.style.cursor = "wait";
                const name = await uploadFile(file);
                slotCounter++;
                media.set(`slot_${slotCounter}`, { name, kind });
            } catch (e) {
                console.error("[MiniMax H3 Vision] Upload error:", e);
            } finally {
                document.body.style.cursor = "default";
            }
        }
        persistState();
        render();
    }

    const box = make("div"); box.className = "mmv-box";
    const promptTextarea = make("textarea");
    promptTextarea.className = "mmv-prompt";
    promptTextarea.placeholder = "Custom Prompt Override (Optional):\nLeave blank for auto-generation.\n- Single-click any media above to insert its reference tag (e.g., <Picture 1>)\n- Double-click a video to insert its audio tag (e.g., <Video Audio 1>)";
    promptTextarea.value = overrideWidget ? (overrideWidget.value || "") : "";

    promptTextarea.oninput = () => {
        if (overrideWidget) {
            overrideWidget.value = promptTextarea.value;
            overrideWidget.callback?.call(overrideWidget, promptTextarea.value);
        }
    };

    promptTextarea.addEventListener('wheel', (e) => { e.stopPropagation(); });
    promptTextarea.addEventListener('pointerdown', (e) => { e.stopPropagation(); });

    function render() {
        box.innerHTML = "";

        const grid = make("div");
        grid.className = "mmv-grid";

        if (media.size === 0) {
            grid.appendChild(addDrop(true));
        } else {
            const typeOrder = { image: 1, video: 2, audio: 3 };
            const entries = [...media.entries()].sort((a, b) => {
                if (typeOrder[a[1].kind] !== typeOrder[b[1].kind]) return typeOrder[a[1].kind] - typeOrder[b[1].kind];
                return a[0].localeCompare(b[0]);
            });
            entries.forEach(([s, e]) => grid.appendChild(card(s, e)));
            grid.appendChild(addDrop(false));
        }

        const statusBar = make("div");
        statusBar.className = "mmv-status-bar";

        const msgNode = make("div", {}, uploadNotice || "\u00A0");
        msgNode.className = "mmv-limit-msg";
        statusBar.appendChild(msgNode);

        if (media.size > 0) {
            const clearBtn = make("div", {}, "✖ Clear All");
            clearBtn.className = "mmv-clear-all";
            clearBtn.title = "Remove all media";
            clearBtn.onclick = e => { e.stopPropagation(); media.clear(); uploadNotice = ""; persistState(); render(); };
            statusBar.appendChild(clearBtn);
        } else if (!uploadNotice) {
            statusBar.style.display = "none";
        }

        grid.appendChild(statusBar);

        box.appendChild(grid);
        requestAnimationFrame(syncNodeHeight);
    }

    root.appendChild(box);
    root.appendChild(promptTextarea);

    const domWidget = node.addDOMWidget("gh_vision_v2_panel", "gh_vision_v2_panel", root, { serialize: false, hideOnZoom: false });
    domWidget.options = domWidget.options || {};
    domWidget.options.serialize = false;

    const getMinDomHeight = () => {
        let boxHeight = box ? box.offsetHeight : 0;
        if (boxHeight === 0 && media) {
            boxHeight = media.size === 0 ? 100 : Math.ceil((media.size + 1) / 4) * 110 + 30;
        }
        return boxHeight + 95;
    };

    domWidget.computeSize = function (width) {
        return [width ? Math.max(WIDTH, width) : WIDTH, getMinDomHeight()];
    };

    const baseComputeSize = node.computeSize.bind(node);
    node.computeSize = function (out) {
        let measured = baseComputeSize(out);
        if (measured[0] < WIDTH) measured[0] = WIDTH;
        return measured;
    };

    const previousOnResize = node.onResize;
    node.onResize = function (...args) {
        if (this.size?.[0] < WIDTH) this.size[0] = WIDTH;
        previousOnResize?.apply(this, args);
        requestAnimationFrame(syncNodeHeight);
    };

    const previousOnDrawBackground = node.onDrawBackground;
    node.onDrawBackground = function (ctx) {
        if (root && this.size) {
            // Explicitly sync DOM width to bypass ComfyUI classic flexbox collapse bugs on click/selection
            const targetWidth = (this.size[0] - 16) + "px";
            if (root.style.width !== targetWidth) {
                root.style.width = targetWidth;
            }

            // Explicitly sync DOM height to allow prompt text area stretching downward
            if (domWidget && domWidget.last_y !== undefined) {
                const targetHeight = Math.max(getMinDomHeight(), this.size[1] - domWidget.last_y - 12) + "px";
                if (root.style.height !== targetHeight) {
                    root.style.height = targetHeight;
                }
            }
        }
        return previousOnDrawBackground?.apply(this, arguments);
    };

    const captureMaterialDrop = event => {
        const target = event.target instanceof Element ? event.target : null;
        const materialArea = target?.closest?.(".mmv-box");
        if (!materialArea || !root.contains(materialArea)) return;
        if (!event.dataTransfer?.types?.includes?.("Files")) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (event.type === "drop") accept(event.dataTransfer.files);
    };

    window.addEventListener("dragenter", captureMaterialDrop, true);
    window.addEventListener("dragover", captureMaterialDrop, true);
    window.addEventListener("drop", captureMaterialDrop, true);

    const oldRemoved = node.onRemoved;
    node.onRemoved = function (...args) {
        window.removeEventListener("dragenter", captureMaterialDrop, true);
        window.removeEventListener("dragover", captureMaterialDrop, true);
        window.removeEventListener("drop", captureMaterialDrop, true);
        return oldRemoved?.apply(this, args);
    };

    render();
    node.setSize([WIDTH, INITIAL_NODE_HEIGHT]);

    return true;
}

app.registerExtension({
    name: "AILab.MiniMaxH3.VisionV2",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE) return;

        const previous = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = previous?.apply(this, arguments);
            if (!this._ghH3PanelReady && createPanel(this)) this._ghH3PanelReady = true;
            return result;
        };
    }
});
