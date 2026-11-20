from django.urls import path

from . import api, views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search_page, name="search"),
    path("entry/<slug:slug>/", views.entry_detail, name="entry"),
    path("entry/<slug:slug>/export.json", views.entry_export, name="entry_export"),
    path("graph/", views.graph_page, name="graph"),
    # REST API
    path("api/search/", api.api_search, name="api_search"),
    path("api/suggest/", api.api_suggest, name="api_suggest"),
    path("api/entry/<slug:slug>/", api.api_entry, name="api_entry"),
    path("api/graph/", api.api_graph, name="api_graph"),
    path("api/stats/", api.api_stats, name="api_stats"),
]
