from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.CensusCreate.as_view(), name='census_create'),
    path('<int:voting_id>/', views.CensusDetail.as_view(), name='census_detail'),
    path('web/', views.listaCensos, name='list_census'),
    path('web/<int:voting_id>/', views.listaVotantes, name='list_cesus_by_voting'),
]