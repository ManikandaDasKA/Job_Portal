import json
import logging
import urllib.parse
import asyncio  # ✅ Required for the continuous background heartbeat task
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("notifications")

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model

        self.user = self.scope.get("user")
        self.heartbeat_task = None # ✅ Placeholder for our continuous keep-alive loop

        if not self.user or self.user.is_anonymous:
            query_string = self.scope.get("query_string", b"").decode("utf-8")
            query_params = urllib.parse.parse_qs(query_string)
            token_list = query_params.get("token") or query_params.get("tokens")

            if token_list:
                raw_token = token_list[0]
                try:
                    validated_token = AccessToken(raw_token)
                    user_id = validated_token.get("user_id")
                    User = get_user_model()
                    self.user = await User.objects.aget(pk=user_id)
                    self.scope["user"] = self.user
                    logger.info(f"[WebSocket Auth] Token verified successfully. User ID: {self.user.user_id}")
                except Exception as auth_err:
                    logger.warning(f"[WebSocket Auth] Token validation failure: {str(auth_err)}")

        if not self.user or self.user.is_anonymous:
            logger.warning("[WebSocket Connect] Anonymous payload rejected.")
            await self.close(code=4030)
            return

        self.user_group_name = f"user_notifications_{self.user.user_id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        # ✅ START CONTINUOUS CONNECTION ENGINE:
        # Launch a non-blocking background task that keeps this specific pipe alive forever
        self.heartbeat_task = asyncio.create_task(self.send_heartbeat_loop())

    async def send_heartbeat_loop(self):
        """
        Sends an invisible ping message down the pipeline every 30 seconds 
        to ensure internet providers/firewalls don't kill the idle connection.
        """
        try:
            while True:
                await asyncio.sleep(30) # Wait 30 seconds
                # Send a tiny, lightweight control string
                await self.send(text_data=json.dumps({"type": "ping"}))
                logger.debug(f"[WebSocket Keep-Alive] Sent ping to User: {self.user.user_id}")
        except asyncio.CancelledError:
            # Caught smoothly when the user disconnects naturally
            pass

    async def disconnect(self, close_code):
        # ✅ FIX: Kill the continuous background loop task so it doesn't leak memory
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        if hasattr(self, 'user_group_name'):
            logger.info(f"[WebSocket Disconnect] Purging room: {self.user_group_name} | Code: {close_code}")
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive(self, text_data):
        # Handle inbound pongs if your frontend replies to your pings
        try:
            data = json.loads(text_data)
            if data.get("type") == "pong":
                logger.debug("Received pong from client.")
        except Exception:
            pass

    async def send_notification(self, event):
        notification_data = event["notification"]
        await self.send(text_data=json.dumps({
            "success": True,
            "data": notification_data
        }))