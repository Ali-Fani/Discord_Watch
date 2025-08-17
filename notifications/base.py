from abc import ABC, abstractmethod

class NotificationProvider(ABC):
    """Base class for notification providers"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the notification provider"""
        pass
    
    @abstractmethod
    async def send_notification(self, user_id: str, message: str) -> bool:
        """Send a notification to a user
        
        Args:
            user_id: The ID of the user to notify
            message: The message to send
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass
