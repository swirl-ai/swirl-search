import asyncio

from django.conf import settings
import cohere
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Batch
from swirl.connectors.connector import Connector
from swirl.connectors.mappings import *
from swirl.connectors.utils import bind_query_mappings

logger = get_task_logger(__name__)
path.append(swirl_setdir())
environ.setdefault('DJANGO_SETTINGS_MODULE', 'swirl_server.settings')
django.setup()


class Qdrant(Connector):
    type = "Qdrant"

    def __init__(self, provider_id, search_id, update, request_id='', resumes=None, jd=None):
        super().__init__(provider_id, search_id, update, request_id)
        self.cohere_key = getattr(settings, 'COHERE_API_KEY', None)
        self.qdrant_key = getattr(settings, 'QDRANT_API_KEY', None)
        self.qdrant_url = getattr(settings, 'QDRANT_URL', None)
        self.cohere = cohere.Client(self.cohere_key)
        self.collection_name = "your_collection_name"
        self.qdrant = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_key,
        )

    def get_embedding(self, text):
        try:
            embeddings = self.cohere.embed([text], "large").embeddings
            return list(map(float, embeddings[0])), len(embeddings[0])
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}", exc_info=True)

    def get_result(self):
        vector, _ = self.get_embedding(self.query_to_provider)

        hits = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=30
        )
        results = []
        for hit in hits:
            result = {
                'text': str(hit.payload),
                'score': hit.score
            }
            results.append(result)
        logger.debug(f"qdrant results={results}")
        final_text = []
        for result in results:
            final_text.append(result["text"][10:])
        return final_text

    def construct_query(self):
        logger.debug(f"{self}: construct_query()")

        self.query_to_provider = self.query_string_to_provider
        logger.info(f"sending query: {self.query_to_provider}")

        return

    def execute_search(self, session=None):
        logger.debug("Started")
        data = self.get_result()
        final_data = [{
            "body": data,
            "title": f"Qdrant_search"
        }]
        logger.debug(f"final data={final_data}")
        self.response = final_data
        logger.info("Finished getting response")

    def normalize_response(self):
        logger.debug(f"{self}: normalize_response()")
        self.results = self.response
        return
