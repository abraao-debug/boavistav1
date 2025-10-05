from django.urls import path
from . import views
#from django.conf import settings
#from django.conf.urls.static import static


app_name = 'materiais'

urlpatterns = [
    # Autenticação
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
path('dashboard/', views.dashboard, name='dashboard'),  
      
    path('minhas-solicitacoes/', views.minhas_solicitacoes, name='minhas_solicitacoes'),  
    path('solicitacoes/', views.lista_solicitacoes, name='lista_solicitacoes'),  
    path('nova-solicitacao/', views.nova_solicitacao, name='nova_solicitacao'),  
    path('analisar-solicitacoes/', views.analisar_solicitacoes, name='analisar_solicitacoes'),  
    path('editar-solicitacao/<int:solicitacao_id>/', views.editar_solicitacao, name='editar_solicitacao'),  
    path('solicitacao/<int:solicitacao_id>/confirmar-envios/', views.confirmar_envios_cotacao, name='confirmar_envios_cotacao'),  
  
    path('aprovar-solicitacao/<int:solicitacao_id>/', views.aprovar_solicitacao, name='aprovar_solicitacao'),  
    path('rejeitar-solicitacao/<int:solicitacao_id>/', views.rejeitar_solicitacao, name='rejeitar_solicitacao'),  
    path('aprovar-parcial/<int:solicitacao_id>/', views.aprovar_parcial, name='aprovar_parcial'),  
    path('analisar/editar/<int:solicitacao_id>/', views.editar_solicitacao_analise, name='analisar_editar_solicitacao'),  
      
    path('historico-aprovacoes/', views.historico_aprovacoes, name='historico_aprovacoes'),  
    path('rejeitar-pelo-escritorio/<int:solicitacao_id>/', views.rejeitar_pelo_escritorio, name='rejeitar_pelo_escritorio'),  
      
    path('api/solicitacao-itens/<int:solicitacao_id>/', views.api_solicitacao_itens, name='api_solicitacao_itens'),  
    path('api/itens-filtrados/', views.api_itens_filtrados, name='api_itens_filtrados'),  
    path('api/solicitacao/<int:solicitacao_id>/detalhes/', views.api_solicitacao_detalhes, name='api_solicitacao_detalhes'),  
    path('api/buscar-fornecedores/', views.api_buscar_fornecedores, name='api_buscar_fornecedores'),  
    path('api/dados-confirmacao-rm/<int:cotacao_id>/', views.api_dados_confirmacao_rm, name='api_dados_confirmacao_rm'),  
    path('api/subcategorias/<int:categoria_id>/', views.api_subcategorias, name='api_subcategorias'),  
    path('api/item-check/', views.api_item_check, name='api_item_check'),  
    path('api/sugerir-categoria/', views.api_sugerir_categoria, name='api_sugerir_categoria'),  
   
    path('gerenciar-cotacoes/', views.gerenciar_cotacoes, name='gerenciar_cotacoes'),  
    path('iniciar-cotacao/<int:solicitacao_id>/', views.iniciar_cotacao, name='iniciar_cotacao'),  
    path('iniciar-cotacao/<int:solicitacao_id>/fornecedor/<int:fornecedor_id>/', views.iniciar_cotacao, name='iniciar_cotacao_fornecedor'),  
    path('cotacao/<int:cotacao_id>/selecionar/', views.selecionar_cotacao_vencedora, name='selecionar_cotacao_vencedora'),  
    path('cotacao/<int:cotacao_id>/rejeitar/', views.rejeitar_cotacao, name='rejeitar_cotacao'),  
    path('solicitacao/<int:solicitacao_id>/enviar-cotacao/', views.enviar_cotacao_fornecedor, name='enviar_cotacao_fornecedor'),  
    path('envio-cotacao/<int:envio_id>/gerar-email/', views.gerar_email_cotacao, name='gerar_email_cotacao'),  
    path('envio-cotacao/<int:envio_id>/confirmar-envio/', views.confirmar_envio_manual, name='confirmar_envio_manual'),  
    path('envio-cotacao/enviar-automatico/', views.enviar_automatico_placeholder, name='enviar_automatico_placeholder'),  
    path('marcar-em-cotacao/<int:solicitacao_id>/', views.marcar_em_cotacao, name='marcar_em_cotacao'),  
    path('selecionar-item-cotado/<int:item_cotado_id>/', views.selecionar_item_cotado, name='selecionar_item_cotado'),  
    path('escritorio/editar-sc/<int:solicitacao_id>/', views.editar_solicitacao_escritorio, name='escritorio_editar_sc'),  
  
    path('requisicoes/', views.gerenciar_requisicoes, name='gerenciar_requisicoes'),  
    path('requisicao/<int:rm_id>/visualizar/', views.visualizar_rm_pdf, name='visualizar_rm_pdf'),  
    path('requisicao/<int:rm_id>/assinar/', views.assinar_requisicao, name='assinar_requisicao'),  
    path('requisicao/<int:rm_id>/enviar-fornecedor/', views.enviar_rm_fornecedor, name='enviar_rm_fornecedor'),  
      
    path('recebimento/registrar/', views.registrar_recebimento, name='registrar_recebimento'),  
    path('api/itens-para-receber/<int:solicitacao_id>/', views.api_get_itens_para_receber, name='api_get_itens_para_receber'),  
    path('historico-recebimentos/', views.historico_recebimentos, name='historico_recebimentos'),      
      
    path('cadastrar-itens/', views.cadastrar_itens, name='cadastrar_itens'),  
    path('editar-item/<int:item_id>/', views.editar_item, name='editar_item'),  
    path('cadastrar-obras/', views.cadastrar_obras, name='cadastrar_obras'),  
    path('gerenciar-fornecedores/', views.gerenciar_fornecedores, name='gerenciar_fornecedores'),  
    path('gerenciar-categorias/', views.gerenciar_categorias, name='gerenciar_categorias'),  
      
    path('fornecedor/<int:fornecedor_id>/editar/', views.editar_fornecedor, name='editar_fornecedor'),  
    path('fornecedor/<int:fornecedor_id>/status/', views.alterar_status_fornecedor, name='alterar_status_fornecedor'),  
  
    path('dashboard/relatorios/', views.dashboard_relatorios, name='dashboard_relatorios'),  
      
    path('excluir-categoria-item/<int:categoria_id>/', views.excluir_categoria_item, name='excluir_categoria_item'),  
    path('recebimento/iniciar/<int:solicitacao_id>/', views.iniciar_recebimento, name='iniciar_recebimento'),  
  
    path('solicitacao/<int:solicitacao_id>/cotacao-agregado/', views.cotacao_agregado, name='cotacao_agregado'),  
    path('solicitacao/<int:solicitacao_id>/dividir-agregado/', views.dividir_solicitacao_agregado, name='dividir_solicitacao_agregado'),  
    path('apagar-item/<int:item_id>/', views.apagar_item, name='apagar_item'),  
  
    path('cadastrar-item-inteligente/', views.cadastrar_item_inteligente_view, name='cadastrar_item_inteligente'),  
    path('cadastrar-item-inteligente/submit/', views.cadastrar_item_inteligente_submit, name='cadastrar_item_inteligente_submit'),  
  
    path('api/sugerir-categoria/', views.api_sugerir_categoria, name='api_sugerir_categoria'),
    ]