-- ============================================================
-- Challenge 1: Add Multimodal Image Embedding Column
-- Run this in AlloyDB Studio to support image-based search
-- ============================================================

-- Add 1408-dimensional image embedding column (multimodalembedding@001)
ALTER TABLE inventory
ADD COLUMN IF NOT EXISTS part_image_embedding vector(1408);

-- Create ScaNN index for image embeddings
SET scann.allow_blocked_operations = true;

CREATE INDEX IF NOT EXISTS idx_inventory_image_scann
ON inventory USING scann (part_image_embedding cosine)
WITH (num_leaves=5, quantizer='sq8');

-- Verify
SELECT part_name,
       (part_embedding IS NOT NULL) as has_text_embedding,
       (part_image_embedding IS NOT NULL) as has_image_embedding
FROM inventory
ORDER BY id;
