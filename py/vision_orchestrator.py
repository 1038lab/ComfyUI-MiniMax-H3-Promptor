"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
"""

from .utils import log_info, log_error, tensor_to_base64


def _get_iterable(media_input):
    """Safely convert ComfyAPI dict/list/tuple/None inputs into a flat iterable."""
    if not media_input:
        return []
    if isinstance(media_input, dict):
        return media_input.values()
    if isinstance(media_input, (list, tuple)):
        return media_input
    return [media_input]


class VisionOrchestrator:
    """
    Stateless orchestrator that dispatches multi-modal LLM calls
    for the H3 Vision Analyzer node.

    All media processing logic (batch images, sequential images, videos,
    and Global Vibe synthesis) is encapsulated here, keeping the node
    endpoint clean.
    """

    def __init__(
        self,
        llm,
        prompt_builder,
        response_parser_cls,
        system_prompt: str,
        vibe_system_prompt: str,
        temperature: float,
        max_tokens: int,
        model_override: str,
    ):
        self.llm = llm
        self.pb = prompt_builder
        self.parser = response_parser_cls
        self.system_prompt = system_prompt
        self.vibe_system_prompt = vibe_system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = model_override

    # ------------------------------------------------------------------
    # Public entry point
    def analyze_all(
        self,
        ref_images,
        ref_videos,
        ref_audios,
        presets: dict,
        overrides: dict,
        global_image_mode: str,
        global_video_mode: str,
        output_language: str,
        batch_size: int,
        provider_label: str,
    ) -> tuple[dict, list]:
        """
        Process all media and return (final_dict, media_keys).

        Parameters
        ----------
        ref_images / ref_videos / ref_audios : ComfyUI Autogrow inputs (dict | list | None)
        presets : loaded vision_prompts.json dict
        overrides : per-key prompt overrides from PromptBuilder.parse_overrides()
        global_image_mode / global_video_mode : preset keys selected in the UI
        output_language : "English" | "Chinese"
        batch_size : Numeric limit for maximum images per API call (1 = sequential)
        provider_label : display label for log messages
        """
        media_keys: list[str] = []
        final_dict: dict = {}

        img_list = [img for img in _get_iterable(ref_images) if img is not None]
        vid_iterable = [vid for vid in _get_iterable(ref_videos) if vid is not None]

        # 1. Process images
        if img_list:
            if batch_size > 1:
                self._process_images_batch(
                    img_list, batch_size, presets, overrides, global_image_mode,
                    output_language, provider_label, media_keys, final_dict,
                )
            else:
                self._process_images_sequential(
                    img_list, presets, overrides, global_image_mode,
                    output_language, provider_label, media_keys, final_dict,
                )

        # 2. Process videos (always one per call)
        if vid_iterable:
            self._process_videos(
                vid_iterable, presets, overrides, global_video_mode,
                output_language, provider_label, media_keys, final_dict,
            )

        # 3. Process audios (dummy registration)
        aud_iterable = [aud for aud in _get_iterable(ref_audios) if aud is not None]
        if aud_iterable:
            aud_index = 1
            for aud in aud_iterable:
                target_key = f"<Audio {aud_index}>"
                media_keys.append(target_key)
                final_dict[target_key] = "[Audio file identified. LLM analysis not supported.]"
                aud_index += 1

        # Embed media keys into final dict for downstream routing
        final_dict["_media_keys"] = media_keys
        return final_dict, media_keys

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_prompt_str(presets: dict, mode: str, is_video: bool = False) -> str:
        dict_key = "video_prompts" if is_video else "image_prompts"
        return presets.get(dict_key, {}).get(mode, "Analyze visually.")

    def _call_llm(self, system_prompt, user_message, payload):
        return self.llm.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            base64_images=payload,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            model=self.model,
        )

    # -- Image: Batch --------------------------------------------------

    def _process_images_batch(
        self, img_list, batch_size, presets, overrides, global_image_mode,
        output_language, provider_label, media_keys, final_dict,
    ):
        """Send images in batch, chunking into requests of max batch_size images to respect API limits."""
        CHUNK_SIZE = batch_size
        sub_batches = [img_list[i:i + CHUNK_SIZE] for i in range(0, len(img_list), CHUNK_SIZE)]
        
        img_index = 1
        for batch_idx, sub_batch in enumerate(sub_batches):
            chunk_keys = []
            instructions = []
            all_frames = []
            pos = 1

            for img in sub_batch:
                target_key = f"<Picture {img_index}>"
                media_keys.append(target_key)
                chunk_keys.append(target_key)
                
                frames = tensor_to_base64(img, max_frames=1)
                active_prompt = overrides.get(target_key, self._get_prompt_str(presets, global_image_mode))
                
                instructions.append(
                    self.pb.build_vision_request(output_language, target_key, active_prompt, pos=pos)
                )
                all_frames.extend(frames)
                img_index += 1
                pos += 1

            mega_prompt = "Order of attached media:\n" + "\n".join(instructions)
            payload = [{"text": mega_prompt}]
            for f in all_frames:
                payload.append({"image": f})

            chunk_label = f"(Chunk {batch_idx+1}/{len(sub_batches)}: {len(chunk_keys)} items)" if len(sub_batches) > 1 else f"({len(chunk_keys)} items)"
            log_info(f"Analyzer calling {provider_label} for IMAGES {chunk_label} in BATCH mode...")
            
            response = self._call_llm(self.system_prompt, "", payload)

            if response.success:
                parsed = self.parser.parse_vision_response(response.content, chunk_keys)
                final_dict.update(parsed)
            else:
                log_error(f"API Error in Image Batch {batch_idx+1}: {response.error}")
                for key in chunk_keys:
                    final_dict[key] = f"API Error: {response.error}"

    # -- Image: Sequential ---------------------------------------------

    def _process_images_sequential(
        self, img_list, presets, overrides, global_image_mode,
        output_language, provider_label, media_keys, final_dict,
    ):
        """Send one image per API request to prevent local VLM OOM / confusion."""
        log_info(f"Analyzer calling {provider_label} for SEQUENTIAL image processing...")
        img_index = 1
        for img in img_list:
            target_key = f"<Picture {img_index}>"
            media_keys.append(target_key)

            frames = tensor_to_base64(img, max_frames=1)
            active_prompt = overrides.get(target_key, self._get_prompt_str(presets, global_image_mode))
            single_prompt = self.pb.build_vision_request(output_language, target_key, active_prompt, pos=1)

            payload = [{"text": single_prompt}]
            for f in frames:
                payload.append({"image": f})

            response = self._call_llm(self.system_prompt, "", payload)

            if response.success:
                parsed = self.parser.parse_vision_response(response.content, [target_key])
                final_dict.update(parsed)
            else:
                log_error(f"API Error in Image {img_index}: {response.error}")
                final_dict[target_key] = f"API Error: {response.error}"

            img_index += 1

    # -- Video ---------------------------------------------------------

    def _process_videos(
        self, vid_iterable, presets, overrides, global_video_mode,
        output_language, provider_label, media_keys, final_dict,
    ):
        """Process each video individually (1 API call per video)."""
        vid_index = 1
        for vid in vid_iterable:
            target_key = f"<Video {vid_index}>"
            media_keys.append(target_key)
            frames = tensor_to_base64(vid, max_frames=4)
            active_prompt = overrides.get(target_key, self._get_prompt_str(presets, global_video_mode, is_video=True))

            mega_prompt = self.pb.build_vision_request(
                output_language, target_key, active_prompt, is_video=True, num_frames=len(frames)
            )
            payload = [{"text": mega_prompt}]
            for f in frames:
                payload.append({"image": f})

            log_info(f"Analyzer calling {provider_label} for {target_key} ({len(frames)} frames)...")
            response = self._call_llm(self.system_prompt, "", payload)

            if response.success:
                parsed = self.parser.parse_vision_response(response.content, [target_key])
                final_dict.update(parsed)
            else:
                log_error(f"API Error in Video {vid_index}: {response.error}")
                final_dict[target_key] = f"API Error: {response.error}"

            vid_index += 1

    # -- Global Vibe ---------------------------------------------------

    def _process_vibe(
        self, presets, overrides, global_image_mode,
        output_language, provider_label, final_dict,
    ):
        """Text-only synthesis call for the Global Vibe summary."""
        # If all visual media analyses failed with API errors, do not call LLM to hallucinate vibe from error text
        visual_entries = [v for k, v in final_dict.items() if not k.startswith("<Audio")]
        if visual_entries and all(str(v).startswith("API Error:") for v in visual_entries):
            log_error("Skipping Global Vibe synthesis because all visual media analyses failed with API errors.")
            final_dict["Global_Vibe"] = "Visual analysis failed for attached media (API Error)."
            return

        vibe_prompt_en = overrides.get("Global_Vibe", self._get_prompt_str(presets, global_image_mode))
        vibe_message = self.pb.build_vibe_request(output_language, final_dict, vibe_prompt_en)

        log_info(f"Analyzer calling {provider_label} for Global Vibe synthesis...")
        vibe_res = self._call_llm(self.vibe_system_prompt, vibe_message, None)

        if vibe_res.success:
            parsed = self.parser.parse_vision_response(vibe_res.content, ["Global_Vibe"])
            final_dict.update(parsed)
        else:
            final_dict["Global_Vibe"] = f"API Error: {vibe_res.error}"
