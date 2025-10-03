from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin

# Importação completa dos modelos
from .models import (
    User, Fornecedor, Obra, CategoriaItem, Tag, UnidadeMedida, ItemCatalogo,
    SolicitacaoCompra, ItemSolicitacao, RequisicaoMaterial,
    ItemRequisicao, ItemRecebimento, Cotacao, ItemCotacao,
    CategoriaSC, HistoricoSolicitacao, EnvioCotacao, DestinoEntrega
)

# --- DEFINIÇÃO DAS CLASSES INLINE PRIMEIRO ---
# É crucial definir estas classes antes que elas sejam usadas nas classes Admin principais.

class ItemSolicitacaoInline(admin.TabularInline):
    model = ItemSolicitacao
    extra = 0
    readonly_fields = ['descricao', 'unidade', 'quantidade', 'observacoes']

class ItemRequisicaoInline(admin.TabularInline):
    model = ItemRequisicao
    extra = 1

class ItemCotacaoInline(admin.TabularInline):
    model = ItemCotacao
    extra = 1
    fields = ('item_solicitacao', 'preco', 'selecionado')


# --- REGISTRO DOS MODELOS PRINCIPAIS ---
@admin.register(User)
class UserAdmin(AuthUserAdmin):
    # Fieldsets para a página de EDIÇÃO de um usuário
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Informações Pessoais", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Datas Importantes", {"fields": ("last_login", "date_joined")}),
        # NOSSA SEÇÃO PERSONALIZADA
        ("Campos Personalizados", {
            "fields": ("perfil", "telefone", "obras", "assinatura_imagem")
        }),
    )
    
    # Fieldsets para a página de CRIAÇÃO de um novo usuário
    add_fieldsets = AuthUserAdmin.add_fieldsets + (
        ('Campos Personalizados', {
            'fields': ('perfil', 'telefone', 'obras', 'assinatura_imagem')
        }),
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'perfil')
    filter_horizontal = ('obras',)

@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ['nome_fantasia', 'razao_social', 'cnpj', 'tipo', 'ativo']
    list_filter = ['ativo', 'tipo', 'estado']
    search_fields = ['nome_fantasia', 'razao_social', 'cnpj']
    list_editable = ['ativo']
    filter_horizontal = ('produtos_fornecidos',)
    
    fieldsets = (
        ('Informações da Empresa', {
            'fields': ('nome_fantasia', 'razao_social', 'cnpj', 'tipo', 'produtos_fornecidos', 'ativo')
        }),
        ('Contato Principal', {
            'fields': ('contato_nome', 'email', 'contato_telefone', 'contato_whatsapp')
        }),
        ('Endereço', {
            'fields': ('cep', 'logradouro', 'numero', 'bairro', 'cidade', 'estado')
        }),
    )

@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ['nome', 'endereco', 'data_inicio', 'data_fim', 'ativa']
    list_filter = ('ativa', 'data_inicio')
    search_fields = ['nome', 'endereco']
    list_editable = ['ativa']

@admin.register(ItemCatalogo)
class ItemCatalogoAdmin(admin.ModelAdmin):
    # Linha 'list_display' atualizada para usar as novas funções
    list_display = ['codigo', 'descricao', 'get_categoria_principal', 'get_subcategoria', 'unidade', 'ativo']
    
    # Filtros aprimorados para permitir filtrar pela categoria principal
    list_filter = ('categoria__categoria_mae', 'ativo')
    
    search_fields = ['codigo', 'descricao']
    list_editable = ['ativo']
    autocomplete_fields = ['categoria', 'unidade']
    filter_horizontal = ('tags',)

    @admin.display(description='Categoria Principal', ordering='categoria__categoria_mae__nome')
    def get_categoria_principal(self, obj):
        if obj.categoria and obj.categoria.categoria_mae:
            return obj.categoria.categoria_mae.nome
        # Se o item está associado a uma categoria principal diretamente
        elif obj.categoria:
            return obj.categoria.nome
        return "-"

    @admin.display(description='Subcategoria', ordering='categoria__nome')
    def get_subcategoria(self, obj):
        # Só exibe subcategoria se houver uma categoria pai
        if obj.categoria and obj.categoria.categoria_mae:
            return obj.categoria.nome
        return "-"

@admin.register(SolicitacaoCompra)
class SolicitacaoCompraAdmin(admin.ModelAdmin):
    list_display = ['numero', 'solicitante', 'obra', 'data_criacao', 'status']
    list_filter = ('status', 'data_criacao', 'obra')
    search_fields = ['numero', 'solicitante__username']
    inlines = [ItemSolicitacaoInline] # Agora funciona, pois a classe foi definida acima
    list_select_related = ['solicitante', 'obra'] # <-- ADICIONE ESTA LINHA

@admin.register(RequisicaoMaterial)
class RequisicaoMaterialAdmin(admin.ModelAdmin):
    list_display = ['numero', 'solicitacao_origem', 'get_fornecedor', 'valor_total', 'status_assinatura', 'data_criacao']
    list_filter = ('status_assinatura', 'data_criacao')
    search_fields = ['numero', 'solicitacao_origem__numero', 'cotacao_vencedora__fornecedor__nome']
    list_select_related = ['solicitacao_origem', 'cotacao_vencedora__fornecedor']
    
    def get_fornecedor(self, obj):
        if obj.cotacao_vencedora and obj.cotacao_vencedora.fornecedor:
            return obj.cotacao_vencedora.fornecedor.nome_fantasia # <--- CORRIGIDO
        return "N/A"
    get_fornecedor.short_description = 'Fornecedor'
    
@admin.register(ItemRecebimento)
class ItemRecebimentoAdmin(admin.ModelAdmin):
    list_display = ['requisicao', 'item_original', 'quantidade_recebida']
    search_fields = ['requisicao__numero', 'item_original__descricao']

@admin.register(Cotacao)
class CotacaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'solicitacao', 'fornecedor', 'data_cotacao', 'valor_total']
    list_filter = ('data_cotacao', 'fornecedor')
    search_fields = ['solicitacao__numero', 'fornecedor__nome_fantasia']
    inlines = [ItemCotacaoInline] # Funciona, pois foi definida acima

@admin.register(ItemCotacao)
class ItemCotacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cotacao', 'item_solicitacao', 'preco', 'selecionado')
    list_filter = ('selecionado', 'cotacao__fornecedor')
    search_fields = ('item_solicitacao__descricao',)

@admin.register(CategoriaSC)
class CategoriaSCAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome']

@admin.register(HistoricoSolicitacao)
class HistoricoSolicitacaoAdmin(admin.ModelAdmin):
    list_display = ('solicitacao', 'timestamp', 'usuario', 'acao')
    list_filter = ('acao', 'timestamp')
    search_fields = ('solicitacao__numero', 'usuario__username')

@admin.register(EnvioCotacao)
class EnvioCotacaoAdmin(admin.ModelAdmin):
    list_display = ('solicitacao', 'fornecedor', 'data_envio', 'prazo_resposta', 'status')
    list_filter = ('status', 'data_envio', 'fornecedor')
    search_fields = ('solicitacao__numero', 'fornecedor__nome_fantasia')
    filter_horizontal = ('itens',)

@admin.register(UnidadeMedida)
class UnidadeMedidaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'sigla']
    search_fields = ['nome', 'sigla']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ['nome']

@admin.register(CategoriaItem)
class CategoriaItemAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'nome', 'categoria_mae']
    list_filter = ['categoria_mae']
    search_fields = ['nome']
    list_display_links = ['__str__']

@admin.register(DestinoEntrega)
class DestinoEntregaAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']

