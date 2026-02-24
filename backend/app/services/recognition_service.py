"""
Recognition Service - CLIP embedding generation and similarity search
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from PIL import Image
import torch



@dataclass
class RecognitionMatch:
    """Similarity match result."""
    label_id: int
    label_name: str
    image_id: int
    image_path: str
    similarity_score: float
    distance_metric: str = "cosine"  # cosine, euclidean


class RecognitionService:
    """Service for CLIP-based recognition and similarity matching."""
    
    def __init__(self):
        """Initialize recognition service with CLIP model."""
        self._model = None
        self._processor = None
        self._device = None
        # DISABLED FOR DEBUGGING - uncomment to enable CLIP
        # self._initialize_model()
    
    def _initialize_model(self):
        """Lazy load CLIP model on first use."""
        if self._model is not None:
            return  # Already initialized
            
        try:
            from transformers import CLIPProcessor, CLIPModel
            
            print("🔄 Loading CLIP model (openai/clip-vit-base-patch32)...")
            
            # Determine device
            if torch.cuda.is_available():
                self._device = "cuda"
                print(f"✅ Using GPU: {torch.cuda.get_device_name(0)}")
            else:
                self._device = "cpu"
                print("⚠️  Using CPU (GPU not available)")
            
            # Load model and processor
            self._model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self._device)
            self._processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", use_fast=True)
            
            # Set to evaluation mode
            self._model.eval()
            
            print(f"✅ CLIP model loaded successfully (device: {self._device})")
            print(f"   Embedding dimension: 512")
            
        except Exception as e:
            print(f"❌ Failed to load CLIP model: {e}")
            raise
    
    def generate_embedding(self, image_path: str) -> List[float]:
        """
        Generate CLIP embedding for a single image.
        
        Args:
            image_path: Absolute path to image file
            
        Returns:
            512-dimensional embedding as list of floats
            
        Raises:
            FileNotFoundError: If image doesn't exist
            Exception: If embedding generation fails
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        try:
            # Load and preprocess image
            image = Image.open(image_path).convert("RGB")
            inputs = self._processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            # Generate embedding (no gradient computation)
            with torch.no_grad():
                image_features = self._model.get_image_features(**inputs)
                
                # Normalize embedding (L2 normalization for cosine similarity)
                embedding = image_features / image_features.norm(dim=-1, keepdim=True)
                
                # Convert to list
                embedding_list = embedding.cpu().numpy()[0].tolist()
            
            return embedding_list
            
        except Exception as e:
            print(f"❌ Failed to generate embedding for {image_path}: {e}")
            raise
    
    def generate_embeddings_batch(self, image_paths: List[str]) -> List[List[float]]:
        """
        Generate CLIP embeddings for multiple images in batch.
        More efficient than calling generate_embedding() multiple times.
        
        Args:
            image_paths: List of absolute paths to image files
            
        Returns:
            List of 512-dimensional embeddings
            
        Raises:
            Exception: If batch processing fails
        """
        try:
            # Load all images
            images = []
            valid_paths = []
            
            for path in image_paths:
                try:
                    img = Image.open(path).convert("RGB")
                    images.append(img)
                    valid_paths.append(path)
                except Exception as e:
                    print(f"⚠️  Skipping {path}: {e}")
            
            if not images:
                return []
            
            # Batch process
            inputs = self._processor(images=images, return_tensors="pt", padding=True)
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            # Generate embeddings
            with torch.no_grad():
                image_features = self._model.get_image_features(**inputs)
                
                # Normalize
                embeddings = image_features / image_features.norm(dim=-1, keepdim=True)
                
                # Convert to list
                embeddings_list = embeddings.cpu().numpy().tolist()
            
            print(f"✅ Generated {len(embeddings_list)} embeddings in batch")
            return embeddings_list
            
        except Exception as e:
            print(f"❌ Batch embedding generation failed: {e}")
            raise
    
    def generate_text_embedding(self, text_query: str) -> List[float]:
        """
        Generate CLIP embedding for a text query.
        Enables semantic search: "a happy child in nature", "futuristic city skyline at night"
        
        Args:
            text_query: Natural language text description
            
        Returns:
            512-dimensional embedding as list of floats
            
        Raises:
            Exception: If embedding generation fails
        """
        try:
            # Preprocess text
            inputs = self._processor(text=[text_query], return_tensors="pt", padding=True)
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            # Generate text embedding
            with torch.no_grad():
                text_features = self._model.get_text_features(**inputs)
                
                # Normalize embedding (L2 normalization for cosine similarity)
                embedding = text_features / text_features.norm(dim=-1, keepdim=True)
                
                # Convert to list
                embedding_list = embedding.cpu().numpy()[0].tolist()
            
            return embedding_list
            
        except Exception as e:
            print(f"❌ Failed to generate text embedding for '{text_query}': {e}")
            raise
    
    def compute_cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between -1 and 1 (1 = identical, 0 = orthogonal, -1 = opposite)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity = dot product (since embeddings are already normalized)
        similarity = np.dot(vec1, vec2)
        
        return float(similarity)
    
    def find_similar_embeddings(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[Tuple[int, List[float]]],  # [(id, embedding), ...]
        top_k: int = 5,
        threshold: float = 0.5
    ) -> List[Tuple[int, float]]:
        """
        Find top-K most similar embeddings to query using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of (id, embedding) tuples to search
            top_k: Number of top matches to return
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (id, similarity_score) sorted by score descending
        """
        query_vec = np.array(query_embedding)
        
        # Compute similarities
        similarities = []
        for candidate_id, embedding in candidate_embeddings:
            candidate_vec = np.array(embedding)
            similarity = float(np.dot(query_vec, candidate_vec))
            
            if similarity >= threshold:
                similarities.append((candidate_id, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top-K
        return similarities[:top_k]
    
    def search_database(
        self,
        query_embedding: List[float],
        db_images: List[Dict[str, Any]],  # [{"id": int, "embedding": List[float], "label_id": int, "label_name": str, "image_path": str}, ...]
        top_k: int = 5,
        threshold: float = 0.5
    ) -> List[RecognitionMatch]:
        """
        Search database for similar images using cosine similarity.
        
        Args:
            query_embedding: Query image embedding
            db_images: List of database images with embeddings and metadata
            top_k: Number of top matches to return
            threshold: Minimum similarity score
            
        Returns:
            List of RecognitionMatch objects sorted by similarity
        """
        query_vec = np.array(query_embedding)
        
        # Compute similarities for all images
        matches = []
        for img_data in db_images:
            if img_data.get("embedding") is None:
                continue
            
            candidate_vec = np.array(img_data["embedding"])
            similarity = float(np.dot(query_vec, candidate_vec))
            
            if similarity >= threshold:
                match = RecognitionMatch(
                    label_id=img_data["label_id"],
                    label_name=img_data["label_name"],
                    image_id=img_data["id"],
                    image_path=img_data["image_path"],
                    similarity_score=similarity,
                    distance_metric="cosine"
                )
                matches.append(match)
        
        # Sort by similarity descending
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Return top-K
        return matches[:top_k]
    
    def search_database_pgvector(
        self,
        query_embedding: List[float],
        catalog_id: int,
        top_k: int = 5,
        threshold: float = 0.5,
        label_filter: Optional[List[int]] = None,
        db_session = None
    ) -> List[RecognitionMatch]:
        """
        Search database using pgvector native similarity search.
        
        Uses PostgreSQL's pgvector extension with cosine distance operator
        for efficient top-K similarity search. Leverages IVFFlat index.
        
        Args:
            query_embedding: Query image embedding (512-dim)
            catalog_id: Recognition catalog ID to search within
            top_k: Number of top matches to return
            threshold: Minimum similarity score (converted from distance)
            label_filter: Optional list of label IDs to restrict search
            db_session: SQLAlchemy session (if None, creates new one)
            
        Returns:
            List of RecognitionMatch objects sorted by similarity
            
        Note:
            Similarity score = 1 - cosine_distance
            Distance range: [0, 2], Similarity range: [1, -1]
            Threshold 0.5 similarity = 0.5 distance
        """
        from app.db import SessionLocal
        from app.models.recognition import RecognitionImage, RecognitionLabel
        
        # Create session if not provided
        close_session = False
        if db_session is None:
            db_session = SessionLocal()
            close_session = True
        
        try:
            # Convert similarity threshold to distance threshold
            # similarity = 1 - distance (for cosine)
            # distance = 1 - similarity
            distance_threshold = 1.0 - threshold
            
            # Build query with pgvector cosine distance operator
            query = db_session.query(
                RecognitionImage.id,
                RecognitionImage.image_path,
                RecognitionImage.thumbnail_path,
                RecognitionLabel.id.label("label_id"),
                RecognitionLabel.label_name,
                RecognitionImage.embedding.cosine_distance(query_embedding).label("distance")
            ).join(
                RecognitionLabel,
                RecognitionImage.label_id == RecognitionLabel.id
            ).filter(
                RecognitionLabel.catalog_id == catalog_id,
                RecognitionImage.is_processed == True,
                RecognitionImage.embedding.isnot(None)
            )
            
            # Apply label filter if specified
            if label_filter:
                query = query.filter(RecognitionLabel.id.in_(label_filter))
            
            # Filter by distance threshold and order by distance (ascending = best match first)
            # Note: Using HAVING would require GROUP BY, so we filter in Python instead
            query = query.order_by(RecognitionImage.embedding.cosine_distance(query_embedding))
            query = query.limit(top_k * 2)  # Fetch extra for threshold filtering
            
            results = query.all()
            
            # Convert to RecognitionMatch objects and apply threshold
            matches = []
            for row in results:
                distance = row.distance
                similarity = 1.0 - distance  # Convert distance to similarity
                
                # Apply similarity threshold
                if similarity >= threshold:
                    match = RecognitionMatch(
                        label_id=row.label_id,
                        label_name=row.label_name,
                        image_id=row.id,
                        image_path=row.image_path,
                        similarity_score=float(similarity),
                        distance_metric="cosine"
                    )
                    matches.append(match)
                
                # Stop if we have enough matches
                if len(matches) >= top_k:
                    break
            
            return matches
            
        finally:
            if close_session:
                db_session.close()
    
    def create_thumbnail(self, image_path: str, thumbnail_path: str, size: Tuple[int, int] = (256, 256)):
        """
        Create a thumbnail from an image.
        
        Args:
            image_path: Path to original image
            thumbnail_path: Path to save thumbnail
            size: Thumbnail size (width, height)
        """
        try:
            img = Image.open(image_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
            
            img.save(thumbnail_path, quality=85, optimize=True)
            
        except Exception as e:
            print(f"⚠️  Failed to create thumbnail for {image_path}: {e}")


# Singleton instance
_recognition_service_instance = None


def get_recognition_service() -> RecognitionService:
    """Get singleton instance of RecognitionService."""
    global _recognition_service_instance
    
    if _recognition_service_instance is None:
        _recognition_service_instance = RecognitionService()
    
    return _recognition_service_instance
