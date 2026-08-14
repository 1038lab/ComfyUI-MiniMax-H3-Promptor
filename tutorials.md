# 🌟 ComfyUI MiniMax H3-Promptor: Master Workflow Tutorials

Welcome to the official advanced workflows guide! The H3-Promptor operates on a "Dual-Brain" architecture (Vision Node + LLM Promptor). Below are classic, production-ready scenarios and exactly how to hook up your nodes and write your descriptions to achieve them.

> *Tip: In future updates, we will include the `.json` ComfyUI workflow files for each of these examples directly in the `example_workflows` folder!*

---

## ✍️ 1. Pure Text-to-Video (T2V)
**Goal:** Generate a highly cinematic video entirely from scratch using only your imagination, without any image or video references.
**Node Setup:**
1. **Vision Analyzer:** Not used. Do not connect it.
2. **H3 Promptor:** 
   - **Task Type:** `Text-to-Video (T2V)`.
   - **Description:** *"A cinematic establishing shot of a neon-lit cyberpunk city in heavy rain. Flying cars zoom past the camera. Deep atmospheric fog, neon reflections on wet pavement, high contrast."*
3. **MiniMax AIO Node:** Do not connect any Images or Audio to the inputs. Just connect the Promptor's output.
**Why this works:** The LLM expands your simple 2-sentence idea into a fully realized, director-level 15-second cinematic shot brief, packed with focal length instructions and lighting aesthetics that the MiniMax generator loves!

---

## 🗣️ 2. The Lip-Sync Presenter (Avatar)
**Goal:** Make a static character image speak directly to the camera, matching an audio track perfectly.
**Node Setup:**
1. **Vision Analyzer:** Connect your Character Image to `image_ref_1`. Set the mode to `Face & Expression Focus`.
2. **H3 Promptor:** 
   - Connect the Vision Analyzer output.
   - **Task Type:** `Image-to-Video Audio Sync (I2VA)`.
   - **Description:** *"The person looks directly into the lens and speaks naturally, matching the rhythm of the audio. Subtle head movements for emphasis."*
3. **MiniMax AIO Node:** Connect the SAME Image and the Audio file.

---

## 🎤 2. The Singer Performance
**Goal:** A character emotionally singing a song, where body language matches vocal intensity.
**Node Setup:**
1. **Vision Analyzer:** Connect Character Image to `image_ref_1`. Set Mode to `Action / Emotion`.
2. **H3 Promptor:** 
   - **Task Type:** `Image-to-Video Audio Sync (I2VA)`.
   - **Description:** *"The character stands on stage bathed in a soft spotlight. They sing passionately, eyes sometimes closing on the high notes. As the music swells, their hands gesture emotionally. Smooth camera push-in."*

---

## 👥 3. Multi-Character Interaction
**Goal:** Two different characters from two different input images interacting in the same scene.
**Node Setup:**
1. **Vision Analyzer:** 
   - Connect Character A to `image_ref_1` (Mode: `Subject / Identity`).
   - Connect Character B to `image_ref_2` (Mode: `Subject / Identity`).
2. **H3 Promptor:**
   - **Task Type:** `Omni Reference (Ref2VA)`.
   - **Description:** *"The man from Picture 1 and the woman from Picture 2 are sitting across a cafe table holding hands. They are laughing together. Focus on their emotional bond. Bright, sunny lighting."*
3. **MiniMax AIO Node:** Batch image A and image B together (in exact order) into the Image input.

---

## � 4. Anime / Realism Style Transfer (Video-to-Video)
**Goal:** Morph a real-life video into an anime style, or vice versa, by transferring the identity from a source image onto the raw motion of the video.
**Node Setup:**
1. **Vision Analyzer:** 
   - Connect your Style/Identity Image to `image_ref_1` (Mode: `Style & Aesthetics`).
   - Connect the Motion Video to `video_ref` (Mode: `Comprehensive`).
2. **H3 Promptor:**
   - **Task Type:** `Reference Video to Audio Sync (Ref2VA)`.
   - **Description:** *"Use the exact physical movements, choreography, and camera tracking from the video, but render it ENTIRELY in the 2D Anime style and character design seen in Picture 1. Smooth 24fps motion, vibrant anime coloring."*

---

## 🏙️ 5. The Cinematic Fly-Through (Environment Layout)
**Goal:** Turn a flat architectural or nature image into a stunning 3D 15-second drone fly-through.
**Node Setup:**
1. **Vision Analyzer:** Connect the Environment Image to `image_ref_1` (Mode: `Cinematic Composition`).
2. **H3 Promptor:**
   - **Task Type:** `Image-to-Video (I2V)`.
   - **Description:** *"An epic drone fly-through of this landscape. The camera starts high and rapidly pushes forward and down, diving through the architectural gaps. Deep depth of field, golden hour lighting, cinematic god rays piercing through the clouds."*

---

## 🌅 6. The Day-to-Night Morph (First/Last Frame)
**Goal:** Magically transition an image taken during the day into the exact same location at night over 10 seconds.
**Node Setup:**
1. **Vision Analyzer:** 
   - Connect the Day Image to `image_ref_1` (Mode: `Color Palette & Texture`).
   - Connect the Night Image to `image_ref_2` (Mode: `Lighting & Camera`).
2. **H3 Promptor:**
   - **Task Type:** `First/Last Frame (FL2VA)`.
   - **Description:** *"A seamless, locked-off static camera time-lapse. The scene transitions perfectly from the bright daylight in Picture 1 to the glowing neon night environment in Picture 2 over the duration of the clip. Shadows stretch and light sources ignite as time accelerates."*
3. **MiniMax AIO Node:** Batch Image 1 and 2 in order.

---

## 📦 7. High-End Product Commercial
**Goal:** A cinematic commercial shot demonstrating a product.
**Node Setup:**
1. **Vision Analyzer:** Connect the Product Image to `image_ref_1` (Mode: `Prop & Object Interaction`).
2. **H3 Promptor:**
   - **Task Type:** `Image-to-Video (I2V)`.
   - **Description:** *"A highly cinematic product commercial shot. The product seen in Picture 1 is resting on a sleek, reflective black marble surface. A slow macro tracking shot rotates around the product. Neon studio lights sweep across its texture, revealing high-end manufacturing details."*

---

## 🎯 8. The "Blind" Multi-Reference (Advanced Force Binding)
**Goal:** You want to feed 6 images into the MiniMax generator, but you only want the Vision Analyzer to process the first 2 (to save time or API costs).
**Node Setup:**
1. **H3 Promptor:** 
   - Leave the Vision Analyzer connected to just your first 2 images.
   - **Crucial Step:** On the Promptor node, manually set the `reference_images` dropdown to **6**.
2. **MiniMax AIO Node:** Connect all 6 images via an Image Batch to the sampler.
**Why this works:** The Promptor will strictly respect your manual **6** override. It will automatically generate the structural binding tags (`<Picture 1>` through `<Picture 6>`) so the MiniMax API knows exactly how many references to fetch for the video, despite the VLM only having detailed readouts for the first two!

---

## ⏪ 9. The Reverse Narrative (Last Frame Inference / L2VA)
**Goal:** You have a specific ending frame (e.g., a person falling into water) and you want the AI to dream up the cinematic sequence that logically led up to that exact moment.
**Node Setup:**
1. **Vision Analyzer:** Connect the Ending Image to `image_ref_1`.
2. **H3 Promptor:** 
   - **Task Type:** Manually select `Last-Frame-to-Video-Audio (L2VA)`. *(Do not leave on Auto).*
   - **Description:** *"A person falling backward into a swimming pool. The sequence starts with them slipping on the wet tile, struggling to balance, and finally falling."*
3. **MiniMax AIO Node:** Connect the SAME Image to the image input.
**Why this works:** Rather than treating your single image as Shot 1, the L2VA structural engine instructs the LLM to reverse-engineer a narrative. It chronologicaly builds up the timeline, ensuring that the *absolute last second* of the video locks perfectly onto the exact pose established by the image you provided.
