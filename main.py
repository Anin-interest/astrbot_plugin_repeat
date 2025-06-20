import base64
from pathlib import Path
import aiohttp

from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.platform import AstrMessageEvent

import astrbot.core.message.components as Comp
from astrbot.core.star.filter.event_message_type import EventMessageType


@register(
    "astrbot_plugin_reply",
    "安音Anin",
    "复读机机人（纯人机喵）",
    "1.0.0",
    "",
)
class RepeatPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.group_list: list[str] = config.get("repeat_group_list", [])
        self.target_list: list[str] = config.get("repeat_target_list", [])
        self.at_list: list[str] = config.get("repeat_at_list", [])

    @filter.event_message_type(EventMessageType.ALL)
    async def repeat_handle(self, event: AstrMessageEvent):
        """
        狠狠复读

        功能描述：
        - 复读发送者的正常消息
        - 根据
        """
        group_id: str = event.get_group_id()
        sender_id: str = event.get_sender_id()
        sender_name: str = event.get_sender_name()
        # 如果没有群ID或者不在群列表中，则不处理
        if not group_id or not group_id in self.group_list:
            return
        # 若发送者不在回复列表中，则不处理
        if not sender_id in self.target_list:
            return

        bot_qq: str = event.get_self_id()
        messages = event.get_messages()
        result = []
        async def _process_segment(_seg):
            """处理消息段"""
            if isinstance(_seg, Comp.Reply):
                # 回复消息段，若回复了at列表中成员发的消息，则回复发送者的消息，否则连并回复一起复读
                msg_id = event.message_obj.message_id
                if not str(_seg.sender_id) in self.at_list:
                    msg_id = _seg.id
                result.append(Comp.Reply(id = msg_id))
            elif isinstance(_seg, Comp.Poke):
                # 戳一戳消息段，如果戳一戳对象的QQ在at列表中，则戳发送者，否则复读（戳？
                if _seg.qq == bot_qq:
                    return
                elif _seg.qq in self.at_list:
                    result.append(Comp.Poke(type=_seg.type, qq=sender_id))
                else:
                    result.append(Comp.Poke(type=_seg.type, qq=_seg.qq))
            elif isinstance(_seg, Comp.Plain):
                # 纯文本消息段直接复读
                result.append(Comp.Plain(_seg.text))
            elif isinstance(_seg, Comp.At):
                # at消息段，检查是否在at列表中，在则At发送者，否则复读被at的QQ号
                if str(_seg.qq) in self.at_list:
                    result.append(Comp.At(qq = sender_id, name=sender_name))
                else:
                    result.append(Comp.At(qq = _seg.qq, name=_seg.name))
            elif isinstance(_seg, Comp.Image):
                # 图片消息段，直接复读
                image : bytes = None
                if hasattr(_seg, "url") and _seg.url:
                    img_url = _seg.url
                    # 如果是有效的本地路径，则直接读取文件
                    if Path(img_url).is_file():
                        with open(img_url, "rb") as f:
                            image = f.read()
                    else:  # 否则尝试作为URL下载
                        if msg_image := await self.download_image(img_url):
                            image = msg_image

                elif hasattr(_seg, "file"):
                    file_content = _seg.file
                    if isinstance(file_content, str):
                        # 如果是有效的本地路径，则直接读取文件
                        if Path(file_content).is_file():
                            with open(file_content, "rb") as f:
                                image = f.read()
                        else:  # 否则尝试作为Base64编码解析
                            if file_content.startswith("base64://"):
                                file_content = file_content[len("base64://") :]
                            file_content = base64.b64decode(file_content)
                    if isinstance(file_content, bytes):
                        image = file_content
                result.append(Comp.Image.fromBytes(image))
            elif isinstance(_seg, Comp.Face):
                # 表情消息段，直接复读
                result.append(Comp.Face(_seg.id))
        # 遍历消息段落
        for seg in messages:
            await _process_segment(seg)

        # 复读
        if result:
            yield event.chain_result(result)

    @staticmethod
    async def download_image(url: str) -> bytes | None:
        """下载图片"""
        url = url.replace("https://", "http://")
        try:
            async with aiohttp.ClientSession() as client:
                response = await client.get(url)
                img_bytes = await response.read()
                return img_bytes
        except Exception as e:
            logger.error(f"图片下载失败: {e}")

