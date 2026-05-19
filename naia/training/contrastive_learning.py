"""Contrastive learning techniques for better representations."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContrastiveLoss(nn.Module):
    """Contrastive loss for representation learning."""
    
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
    
    def forward(
        self,
        embeddings1: torch.Tensor,
        embeddings2: torch.Tensor,
        labels: torch.Tensor,
    ) -> torch.Tensor:
        """Compute contrastive loss."""
        # Normalize embeddings
        embeddings1 = F.normalize(embeddings1, dim=1)
        embeddings2 = F.normalize(embeddings2, dim=1)
        
        # Compute similarity matrix
        logits = torch.matmul(embeddings1, embeddings2.t()) / self.temperature
        
        # Compute loss
        loss = F.cross_entropy(logits, labels)
        
        return loss


class InfoNCELoss(nn.Module):
    """InfoNCE loss for contrastive learning."""
    
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
    
    def forward(
        self,
        z_i: torch.Tensor,
        z_j: torch.Tensor,
    ) -> torch.Tensor:
        """Compute InfoNCE loss."""
        batch_size = z_i.shape[0]
        
        # Concatenate positive pairs
        z = torch.cat([z_i, z_j], dim=0)
        
        # Normalize
        z = F.normalize(z, dim=1)
        
        # Compute similarity matrix
        similarity = torch.matmul(z, z.t()) / self.temperature
        
        # Create labels
        labels = torch.arange(batch_size, device=z.device)
        labels = torch.cat([labels, labels], dim=0)
        
        # Mask out self-similarity
        mask = torch.eye(2 * batch_size, device=z.device).bool()
        similarity.masked_fill_(mask, -float('inf'))
        
        # Compute loss
        loss = F.cross_entropy(similarity, labels)
        
        return loss


class SimCLRLoss(nn.Module):
    """SimCLR loss for contrastive learning."""
    
    def __init__(self, temperature: float = 0.5):
        super().__init__()
        self.temperature = temperature
    
    def forward(
        self,
        z_i: torch.Tensor,
        z_j: torch.Tensor,
    ) -> torch.Tensor:
        """Compute SimCLR loss."""
        batch_size = z_i.shape[0]
        
        # Concatenate
        z = torch.cat([z_i, z_j], dim=0)
        
        # Normalize
        z = F.normalize(z, dim=1)
        
        # Compute similarity
        similarity = torch.matmul(z, z.t()) / self.temperature
        
        # Positive pairs
        pos_sim = torch.diag(similarity, batch_size)
        pos_sim = torch.cat([pos_sim, pos_sim], dim=0)
        
        # Negative pairs
        neg_mask = ~torch.eye(2 * batch_size, device=z.device).bool()
        neg_sim = similarity[neg_mask].view(2 * batch_size, -1)
        
        # Compute loss
        logits = torch.cat([pos_sim.unsqueeze(1), neg_sim], dim=1)
        labels = torch.zeros(2 * batch_size, dtype=torch.long, device=z.device)
        
        loss = F.cross_entropy(logits, labels)
        
        return loss


class ProjectionHead(nn.Module):
    """Projection head for contrastive learning."""
    
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 256,
        output_dim: int = 128,
    ):
        super().__init__()
        self.projection = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Project input to contrastive space."""
        return self.projection(x)


class ContrastiveLearningTrainer:
    """Trainer for contrastive learning."""
    
    def __init__(
        self,
        model: nn.Module,
        tokenizer: Any,
        projection_dim: int = 128,
        temperature: float = 0.07,
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.projection_head = ProjectionHead(
            input_dim=model.config.hidden_size,
            output_dim=projection_dim,
        )
        self.loss_fn = InfoNCELoss(temperature=temperature)
    
    def encode(self, text: str) -> torch.Tensor:
        """Encode text to embedding."""
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            embeddings = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        
        return embeddings
    
    def augment_text(self, text: str) -> str:
        """Augment text for contrastive learning."""
        # Simplified augmentation
        # In production, use more sophisticated techniques
        words = text.split()
        
        # Random word swap
        if len(words) > 1:
            idx1, idx2 = torch.randint(0, len(words), (2,)).tolist()
            words[idx1], words[idx2] = words[idx2], words[idx1]
        
        return " ".join(words)
    
    def train_step(
        self,
        batch: list[dict[str, str]],
        optimizer: torch.optim.Optimizer,
    ) -> float:
        """Training step for contrastive learning."""
        # Encode original texts
        original_texts = [ex.get("input", ex.get("instruction", "")) for ex in batch]
        original_embeddings = torch.stack([self.encode(text) for text in original_texts])
        
        # Encode augmented texts
        augmented_texts = [self.augment_text(text) for text in original_texts]
        augmented_embeddings = torch.stack([self.encode(text) for text in augmented_texts])
        
        # Project to contrastive space
        z_i = self.projection_head(original_embeddings)
        z_j = self.projection_head(augmented_embeddings)
        
        # Compute loss
        loss = self.loss_fn(z_i, z_j)
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        return loss.item()


class SupervisedContrastiveLoss(nn.Module):
    """Supervised contrastive loss."""
    
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
    
    def forward(
        self,
        embeddings: torch.Tensor,
        labels: torch.Tensor,
    ) -> torch.Tensor:
        """Compute supervised contrastive loss."""
        # Normalize
        embeddings = F.normalize(embeddings, dim=1)
        
        # Compute similarity
        similarity = torch.matmul(embeddings, embeddings.t()) / self.temperature
        
        # Create mask for positive pairs
        labels = labels.unsqueeze(1)
        mask = labels == labels.t()
        
        # Mask out self-similarity
        mask = mask & ~torch.eye(len(labels), device=labels.device).bool()
        
        # Compute loss
        exp_sim = torch.exp(similarity) * mask
        sum_exp_sim = exp_sim.sum(dim=1, keepdim=True)
        log_prob = similarity - torch.log(sum_exp_sim)
        
        # Mean over positive pairs
        mean_log_prob_pos = (mask * log_prob).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        loss = -mean_log_prob_pos.mean()
        
        return loss


class MomentumContrast(nn.Module):
    """Momentum contrast (MoCo) for contrastive learning."""
    
    def __init__(
        self,
        encoder: nn.Module,
        momentum_encoder: nn.Module,
        queue_size: int = 65536,
        temperature: float = 0.07,
        momentum: float = 0.999,
    ):
        super().__init__()
        self.encoder = encoder
        self.momentum_encoder = momentum_encoder
        self.queue_size = queue_size
        self.temperature = temperature
        self.momentum = momentum
        
        # Initialize queue
        self.register_buffer("queue", torch.randn(queue_size, encoder.config.hidden_size))
        self.queue = F.normalize(self.queue, dim=0)
        self.register_buffer("queue_ptr", torch.zeros(1, dtype=torch.long))
    
    @torch.no_grad()
    def _momentum_update(self):
        """Update momentum encoder."""
        for param_q, param_k in zip(
            self.encoder.parameters(),
            self.momentum_encoder.parameters(),
        ):
            param_k.data = param_k.data * self.momentum + param_q.data * (1 - self.momentum)
    
    @torch.no_grad()
    def _dequeue_and_enqueue(self, keys: torch.Tensor):
        """Update queue with new keys."""
        batch_size = keys.shape[0]
        
        ptr = int(self.queue_ptr)
        assert self.queue_size % batch_size == 0
        
        # Replace keys in queue
        self.queue[ptr:ptr + batch_size] = keys
        ptr = (ptr + batch_size) % self.queue_size
        self.queue_ptr[0] = ptr
    
    def forward(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
    ) -> torch.Tensor:
        """Forward pass with momentum contrast."""
        # Compute query embeddings
        q = self.encoder(q)
        q = F.normalize(q, dim=1)
        
        # Compute key embeddings with momentum encoder
        with torch.no_grad():
            self._momentum_update()
            k = self.momentum_encoder(k)
            k = F.normalize(k, dim=1)
        
        # Compute positive logits
        l_pos = torch.einsum('nc,nc->n', [q, k]).unsqueeze(-1)
        
        # Compute negative logits
        l_neg = torch.einsum('nc,ck->nk', [q, self.queue.clone().detach()])
        
        # Concatenate
        logits = torch.cat([l_pos, l_neg], dim=1) / self.temperature
        
        # Labels (first is positive)
        labels = torch.zeros(logits.shape[0], dtype=torch.long, device=q.device)
        
        # Compute loss
        loss = F.cross_entropy(logits, labels)
        
        # Update queue
        self._dequeue_and_enqueue(k)
        
        return loss


def run_contrastive_pretraining(
    dataset_path: str,
    model_name: str,
    output_dir: str,
    epochs: int = 10,
) -> dict[str, Any]:
    """Run contrastive pretraining."""
    logger.info(f"Running contrastive pretraining with {model_name}")
    
    # Load model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    
    # Load dataset
    with open(dataset_path, encoding="utf-8") as f:
        examples = json.load(f)
    
    # Setup contrastive trainer
    trainer = ContrastiveLearningTrainer(
        model=model,
        tokenizer=tokenizer,
        projection_dim=128,
        temperature=0.07,
    )
    
    # Setup optimizer
    optimizer = torch.optim.AdamW(
        list(model.parameters()) + list(trainer.projection_head.parameters()),
        lr=1e-4,
    )
    
    # Training loop
    logger.info("Starting contrastive pretraining...")
    
    for epoch in range(epochs):
        total_loss = 0
        num_batches = len(examples) // 32
        
        for i in range(0, len(examples), 32):
            batch = examples[i:i + 32]
            loss = trainer.train_step(batch, optimizer)
            total_loss += loss
        
        avg_loss = total_loss / num_batches
        logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.4f}")
    
    # Save model
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)
    
    logger.info(f"Contrastive pretraining complete. Model saved to {output_path}")
    
    return {
        "status": "success",
        "output_dir": str(output_path),
        "epochs": epochs,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Run contrastive pretraining
    result = run_contrastive_pretraining(
        dataset_path="dataset/output/train_set.json",
        model_name="Qwen/Qwen2.5-1.5B-Instruct",
        output_dir="models/naia-contrastive-pretrained",
        epochs=5,
    )
    
    print("\n=== Contrastive Pretraining Complete ===")
    print(json.dumps(result, indent=2))
