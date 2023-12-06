'''
@author:     Sid Probstein
@contact:    sid@swirl.today
'''

from django.db import models
from django.urls import reverse

def getSearchProviderQueryProcessorsDefault():
    return ["AdaptiveQueryProcessor"]

def getSearchProviderResultProcessorsDefault():
    return ["MappingResultProcessor","DateFinderResultProcessor","CosineRelevancyResultProcessor"]

class FlexibleChoiceField(models.CharField):
    """
    Allow choices and free text so we can have a user named and shared query transform
    in a seacrh provider
    """
    def __init__(self, *args, **kwargs):
        self.custom_choices = kwargs.pop("choices", [])
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["choices"] = self.custom_choices
        return name, path, args, kwargs

    def to_python(self, value):
        if value in dict(self.custom_choices):
            return value
        return super().to_python(value)

    def validate(self, value, model_instance):
        if value not in dict(self.custom_choices):
            return super().validate(value, model_instance)

class Authenticator(models.Model):
    name = models.CharField(max_length=100)

class OauthToken(models.Model):
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    idp = models.CharField(max_length=32, default='Microsoft')
    token = models.CharField(max_length=4096)
    refresh_token = models.CharField(max_length=4096, blank=True, null=True)
    class Meta:
        unique_together = [['owner', 'idp']]

class SearchProvider(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    shared = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)
    default = models.BooleanField(default=True)
    AUTHENTICATOR_CHOICES = [
        ('Microsoft', 'Microsoft Authentication')
    ]
    authenticator = models.CharField(max_length=200, default='', blank=True, choices=AUTHENTICATOR_CHOICES)
    CONNECTORS_AUTHENTICATORS = dict({
        'M365OutlookMessages': 'Microsoft',
        'M365OneDrive': 'Microsoft',
        'M365OutlookCalendar': 'Microsoft',
        'M365SharePointSites': 'Microsoft',
        'MicrosoftTeams': 'Microsoft',
    })
    CONNECTOR_CHOICES = [
        ('ChatGPT', 'ChatGPT Query String'),
        ('RequestsGet', 'HTTP/GET returning JSON'),
        ('RequestsPost', 'HTTP/POST returning JSON'),
        ('Elastic', 'Elasticsearch Query String'),
        ('OpenSearch', 'OpenSearch Query String'),
        # Uncomment the line below to enable PostgreSQL
        # ('PostgreSQL', 'PostgreSQL'),
        #('Qdrant', 'Qdrant'),
        #('Discord', 'Discord'),
        ('BigQuery', 'Google BigQuery'),
        ('Sqlite3', 'Sqlite3'),
        ('M365OutlookMessages', 'M365 Outlook Messages'),
        ('M365OneDrive', 'M365 One Drive'),
        ('M365OutlookCalendar', 'M365 Outlook Calendar'),
        ('M365SharePointSites', 'M365 SharePoint Sites'),
        ('MicrosoftTeams', 'Microsoft Teams'),
    ]
    connector = models.CharField(max_length=200, default='RequestsGet', choices=CONNECTOR_CHOICES)
    url = models.CharField(max_length=2048, default=str, blank=True)
    query_template = models.CharField(max_length=2048, default='{url}?q={query_string}', blank=True)
    post_query_template = models.JSONField(default={}, blank=True)
    QUERY_PROCESSOR_CHOICES = [
        ('GenericQueryProcessor', 'GenericQueryProcessor'),
        ('TestQueryProcessor', 'TestQueryProcessor'),
        ('AdaptiveQueryProcessor', 'AdaptiveQueryProcessor'),
        ('SpellcheckQueryProcessor', 'SpellcheckQueryProcessor')
    ]
    query_processors = models.JSONField(default=getSearchProviderQueryProcessorsDefault, blank=True)
    query_mappings = models.CharField(max_length=2048, default=str, blank=True)
    RESULT_PROCESSOR_CHOICES = [
        ('GenericResultProcessor', 'GenericResultProcessor'),
        ('DuplicateHalfResultProcessor', 'DuplicateHalfResultProcessor'),
        ('TestResultProcessor', 'TestResultProcessor'),
        ('MappingResultProcessor', 'MappingResultProcessor'),
        ('DateFinderResultProcessor','DateFinderResultProcessor'),
        ('DedupeByFieldResultProcessor', 'DedupeByFieldResultProcessor'),
        ('LenLimitingResultProcessor', 'LenLimitingResultProcessor'),
        ('CleanTextResultProcessor','CleanTextResultProcessor'),
        ('CosineRelevancyResultProcessor','CosineRelevancyResultProcessor')
    ]
    response_mappings = models.CharField(max_length=2048, default=str, blank=True)

    ## if set, and the field exists in the results set, records w/ the same value will
    ## be grouped together and only one result will be returned to the caller

    result_grouping_field = models.CharField(max_length=1024, default=str, blank=True)
    result_processors = models.JSONField(default=getSearchProviderResultProcessorsDefault, blank=True)
    result_mappings = models.CharField(max_length=2048, default=str, blank=True)
    results_per_query = models.IntegerField(default=10)
    eval_credentials = models.CharField(max_length=100, default=str, blank=True)
    credentials = models.CharField(max_length=512, default=str, blank=True)
    tags = models.JSONField(default=list)
    http_request_headers = models.JSONField(default={}, blank=True)
    page_fetch_config_json = models.JSONField(default={}, blank=True)

    class Meta:
        ordering = ['id']

    def get_absolute_url(self):
        # Returns the URL to access
        return reverse('model-detail-view', args=[str(self.id)])

    def __str__(self):
        return self.name

def getSearchPreQueryProcessorsDefault():
    return []

def getSearchPostResultProcessorsDefault():
    return ["DedupeByFieldPostResultProcessor","CosineRelevancyPostResultProcessor"]

class Search(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    query_string = models.CharField(max_length=256, default=str)
    query_string_processed = models.CharField(max_length=256, default=str, blank=True)
    SORT_CHOICES = [
        ('relevancy', 'relevancy'),
        ('date', 'date')
    ]
    sort = models.CharField(max_length=50, default='relevancy', blank=True)
    results_requested = models.IntegerField(default=10)
    searchprovider_list = models.JSONField(default=list, blank=True)
    subscribe = models.BooleanField(default=False)
    status = models.CharField(max_length=50, default='NEW_SEARCH')
    time = models.FloatField(default=0.0)
    PRE_QUERY_PROCESSOR_CHOICES = [
        ('ChatGPTQueryProcessor', 'ChatGPTQueryProcessor'),
        ('GenericQueryProcessor', 'GenericQueryProcessor'),
        ('TestQueryProcessor', 'TestQueryProcessor'),
        ('SpellcheckQueryProcessor', 'SpellcheckQueryProcessor')
    ]
    pre_query_processors = models.JSONField(default=getSearchPreQueryProcessorsDefault, blank=True)
    POST_RESULT_PROCESSOR_CHOICES = [
        ('CosineRelevancyPostResultProcessor', 'CosineRelevancyPostResultProcessor'),
        ('DedupeByFieldPostResultProcessor', 'DedupeByFieldPostResultProcessor'),
        ('DedupeBySimilarityPostResultProcessor', 'DedupeBySimilarityPostResultProcessor'),
    ]
    post_result_processors = models.JSONField(default=getSearchPostResultProcessorsDefault, blank=True)
    result_url = models.CharField(max_length=2048, default='/swirl/results?search_id=%d&result_mixer=%s', blank=True)
    new_result_url = models.CharField(max_length=2048, default='/swirl/results?search_id=%d&result_mixer=RelevancyNewItemsMixer', blank=True)
    messages = models.JSONField(default=list, blank=True)
    MIXER_CHOICES = [
        ('DateMixer', 'DateMixer'),
        ('DateNewItemsMixer', 'DateNewItemsMixer'),
        ('RelevancyMixer', 'RelevancyMixer'),
        ('RelevancyNewItemsMixer', 'RelevancyNewItemsMixer'),
        ('RoundRobinMixer', 'RoundRobinMixer'),
        ('Stack1Mixer', 'Stack1Mixer'),
        ('Stack2Mixer', 'Stack2Mixer'),
        ('Stack3Mixer', 'Stack3Mixer'),
        ('StackNMixer', 'StackNMixer')
    ]
    result_mixer = models.CharField(max_length=200, default='RelevancyMixer', choices=MIXER_CHOICES)
    RETENTION_CHOICES = [
        (0, 'Never expire'),
        (1, 'Expire after 1 hour'),
        (2, 'Expire after 1 day'),
        (3, 'Expire after 1 month')
    ]
    retention = models.IntegerField(default=0, choices=RETENTION_CHOICES)
    tags = models.JSONField(default=list)

    class Meta:
        ordering = ['-date_updated']

    def get_absolute_url(self):
        # Returns the URL to access
        return reverse('model-detail-view', args=[str(self.id)])

    def __str__(self):
        signature = str(self.id) + ':' + str(self.searchprovider_list) + ':' + self.query_string
        return signature

class Result(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    search_id = models.ForeignKey(Search, on_delete=models.CASCADE)
    provider_id = models.IntegerField(default=0)
    searchprovider = models.CharField(max_length=50, default=str)
    query_string_to_provider = models.CharField(max_length=256, default=str)
    result_processor_json_feedback = models.JSONField(default=list)
    query_to_provider = models.CharField(max_length=2048, default=str)
    query_processors = models.JSONField(default=list, blank=True)
    result_processors = models.JSONField(default=list, blank=True)
    messages = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, default=str)
    retrieved = models.IntegerField(default=0)
    found = models.IntegerField(default=0)
    time = models.FloatField(default=0.0)
    json_results = models.JSONField(default=list)
    tags = models.JSONField(default=list)

    class Meta:
        ordering = ['-date_updated']

    def get_absolute_url(self):
        # Returns the URL to access
        return reverse('model-detail-view', args=[str(self.id)])

    def __str__(self):
        signature = str(self.id) + ':' + str(self.search_id) + ':' + str(self.searchprovider)
        return signature

class QueryTransform(models.Model) :
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    shared = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    QUERY_TRASNSFORM_TYPE_CHOICES = [
        ('rewrite', 'Rewrite'),
        ('synonym', 'Synonym' ),
        ('bag', 'Synonym Bag' )
    ]
    qrx_type =  models.CharField(max_length=64, default='rewrite', choices=QUERY_TRASNSFORM_TYPE_CHOICES)
    config_content = models.TextField()
    class Meta:
        unique_together = [
            ('name', 'qrx_type'),
        ]
