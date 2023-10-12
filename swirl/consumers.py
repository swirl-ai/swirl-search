import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from swirl.models import Result, Search
from swirl.processors import *
import asyncio

class Consumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            if not self.scope['user'].is_authenticated or not self.scope['search_id']:
                await self.close(code=403)

            self.room_group_name = f"connection_{self.scope['search_id']}"

            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
        except Exception as e:
            await self.close(code=403) 
            

    async def disconnect(self, code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def get_rag_result(self, search_id, rag_query_items):
        search = Search.objects.get(id=search_id)
        isRagIncluded = "RAGPostResultProcessor" in search.post_result_processors
        isRagItemsUpdated = False
        try:
            rag_result = Result.objects.get(search_id=search_id, searchprovider='ChatGPT')
            isRagItemsUpdated = True
            isRagItemsUpdated = not(set(rag_result.json_results[0]['rag_query_items']) == set(rag_query_items))
        except:
            pass
        if isRagIncluded and not isRagItemsUpdated:
            while 1:
                try:
                    rag_result = Result.objects.get(search_id=search_id, searchprovider='ChatGPT')
                    if rag_result:
                        if rag_result.json_results[0]['body'][0]:
                            return rag_result.json_results[0]['body'][0]
                        return False
                    asyncio.sleep(0.5)
                    continue
                except:
                    asyncio.sleep(0.5)
                    continue
        else:
            try:
                rag_result = Result.objects.get(search_id=search_id, searchprovider='ChatGPT')
                isRagItemsUpdated = not(set(rag_result.json_results[0]['rag_query_items']) == set(rag_query_items))
                if rag_result and not isRagItemsUpdated:
                    if rag_result.json_results[0]['body'][0]:
                        return rag_result.json_results[0]['body'][0]
                    return False
            except:
                pass
            rag_processor = RAGPostResultProcessor(search_id=search_id, request_id='', is_socket_logic=True, rag_query_items=rag_query_items)
            if rag_processor.validate():
                result = rag_processor.process(should_return=True)
                try:
                    return result.json_results[0]['body'][0]
                except:
                    return False
                


    async def receive(self, text_data):
        try:
            result = await self.get_rag_result(self.scope['search_id'], self.scope['rag_query_items'])
            if result:
                await self.send(text_data=json.dumps({
                    'message': result
                }))
            else:
                await self.send(text_data=json.dumps({
                    'message': 'No data'
                }))
        except:
            await self.send(text_data=json.dumps({
                'message': 'No data'
            }))