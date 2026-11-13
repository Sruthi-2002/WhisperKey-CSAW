# WhisperKey Attack Lab (interactive demo)

Open `index.html` in any web browser. It is a self-contained, in-browser model of
the trojaned LES accelerator built from the recovered cipher.

- **Step 1 - Normal operation:** encrypt/decrypt a 32-bit word. The trojaned chip
  is bit-identical to a clean one here.
- **Step 2 - Send the trigger (0x1337C0DE):** arms the trojan; the embedded key
  0x8E043CB1 shifts out over MISO.
- **Step 3 - Decrypt captured traffic** with the stolen key.

The page self-checks its cipher against the challenge test vector
(0x59C359C3 -> 0x9CD84392) on load. No build step, no dependencies.
