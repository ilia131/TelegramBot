from enum import StrEnum


class OrderStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_TRANSFER = "awaiting_transfer"
    AWAITING_RECEIPT = "awaiting_receipt"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    AWAITING_PROVISIONING = "awaiting_provisioning"
    PROVISIONED = "provisioned"
    CANCELLED = "cancelled"
