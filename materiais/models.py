import os
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.db import transaction
from . import rm_config # Importa o novo rm_config
class User(AbstractUser):
    PERFIL_CHOICES = [
        ('almoxarife_obra', 'Almoxarife da Obra'),
        ('engenheiro', 'Engenheiro'),
        ('almoxarife_escritorio', 'Almoxarife do Escritório'),
        ('diretor', 'Diretor'),
    ]
    perfil = models.CharField(max_length=30, choices=PERFIL_CHOICES)
    telefone = models.CharField(max_length=15, blank=True)
    obras = models.ManyToManyField('Obra', blank=True, related_name='usuarios')
    assinatura_imagem = models.ImageField(upload_to='assinaturas/', null=True, blank=True, verbose_name="Imagem da Assinatura")

    def __str__(self):
        return f"{self.username} - {self.get_perfil_display()}"


class DestinoEntrega(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome do Local")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Destino de Entrega"
        verbose_name_plural = "Destinos de Entrega"

class Fornecedor(models.Model):
    TIPO_CHOICES = [
        ('material', 'Material'),
        ('servico', 'Serviço'),
        ('ambos', 'Ambos'),
    ]
    
    nome_fantasia = models.CharField(max_length=200, verbose_name="Nome Fantasia")
    razao_social = models.CharField(max_length=200, verbose_name="Razão Social")
    cnpj = models.CharField(max_length=18, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='material', verbose_name="Tipo")
    produtos_fornecidos = models.ManyToManyField(
        'CategoriaItem',
        blank=True,
        verbose_name="Produtos/Serviços Fornecidos",
        limit_choices_to={'categoria_mae__isnull': False}
    )
    email = models.EmailField()
    contato_nome = models.CharField(max_length=100, blank=True, verbose_name="Nome do Contato")
    contato_telefone = models.CharField(max_length=15, blank=True, verbose_name="Telefone do Contato")
    contato_whatsapp = models.CharField(max_length=15, blank=True, verbose_name="WhatsApp do Contato")
    cep = models.CharField(max_length=9, blank=True, verbose_name="CEP")
    logradouro = models.CharField(max_length=255, blank=True, verbose_name="Logradouro")
    numero = models.CharField(max_length=20, blank=True, verbose_name="Número")
    bairro = models.CharField(max_length=100, blank=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, verbose_name="UF")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome_fantasia

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"


class Obra(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome da Obra")
    endereco = models.CharField(max_length=200, blank=True, verbose_name="Endereço")
    data_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de Fim")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Obra"
        verbose_name_plural = "Obras"


class CategoriaItem(models.Model):
    nome = models.CharField(max_length=100)
    categoria_mae = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='subcategorias'
    )
    embedding = models.JSONField(null=True, blank=True, editable=False) # Armazenará o vetor numérico
    
    def __str__(self):
        if self.categoria_mae:
            return f"{self.categoria_mae} -> {self.nome}"
        return self.nome

    class Meta:
        verbose_name = "Categoria de Item"
        verbose_name_plural = "Categorias de Itens"
        unique_together = ('nome', 'categoria_mae',)

class UnidadeMedida(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    sigla = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"{self.nome} ({self.sigla})"

    class Meta:
        verbose_name = "Unidade de Medida"
        verbose_name_plural = "Unidades de Medida"

class CategoriaSC(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Categoria de SC"
        verbose_name_plural = "Categorias de SC"
        
class Tag(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

class ItemCatalogo(models.Model):
    codigo = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Código")
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    categoria = models.ForeignKey(
        CategoriaItem,
        on_delete=models.PROTECT, 
        verbose_name="Categoria"
    )
    unidade = models.ForeignKey(
        UnidadeMedida, 
        on_delete=models.PROTECT,
        verbose_name="Unidade Padrão",
        null=True,
        blank=True
    )
    tags = models.ManyToManyField(Tag, blank=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    # --- ADICIONE ESTA LINHA ---
    is_agregado = models.BooleanField(default=False, verbose_name="É Agregado?")

    def save(self, *args, **kwargs):
        if not self.codigo:
            prefixo = self.categoria.nome[:3].upper() if self.categoria else "GER"
            ultimo_item = ItemCatalogo.objects.all().order_by('id').last()
            proximo_id = (ultimo_item.id + 1) if ultimo_item else 1
            self.codigo = f"{prefixo}-{proximo_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"

    class Meta:
        verbose_name = "Item do Catálogo"
        verbose_name_plural = "Itens do Catálogo"

class SolicitacaoCompra(models.Model):
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('pendente_aprovacao', 'Pendente de Aprovação'),
        ('aprovado_engenharia', 'Aprovado - Engenharia'),
        ('aprovada', 'Cotação - Para Iniciar'),
        ('rejeitada', 'Rejeitada'),
        ('em_cotacao', 'Cotação - Em Andamento'),
        ('aguardando_resposta', 'Cotação - Aguardando Resposta'),
        ('cotacao_selecionada', 'Cotação - Recebida/Analisar'),
        ('finalizada', 'RM Gerada'),
        ('a_caminho', 'A Caminho'),
        ('recebida_parcial', 'Recebida Parcialmente'),  # <-- NOVO STATUS ADICIONADO
        ('recebida', 'Recebida'),
    ]
    numero = models.CharField(max_length=100, unique=True, blank=True, verbose_name="Código")
    solicitante = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitacoes')
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, null=True, blank=True)
    destino = models.ForeignKey(
        DestinoEntrega,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Destino de Entrega"
    )
    categoria_sc = models.ForeignKey(
        CategoriaSC, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Categoria da SC"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_necessidade = models.DateField()
    justificativa = models.TextField(verbose_name="Observação Geral")
    is_emergencial = models.BooleanField(default=False, verbose_name="Solicitação Emergencial")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rascunho')
    aprovador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='aprovacoes')
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    observacoes_aprovacao = models.TextField(blank=True)
    data_recebimento = models.DateTimeField(null=True, blank=True, verbose_name="Data de Recebimento")
    recebedor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Recebedor", null=True, blank=True)
    sc_mae = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='scs_filhas'
    )

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                if self.sc_mae:
                    num_filhas = SolicitacaoCompra.objects.select_for_update().filter(sc_mae=self.sc_mae).count()
                    self.numero = f"{self.sc_mae.numero}-F{num_filhas + 1}"
                else:
                    hoje = timezone.now().date()
                    data_str = hoje.strftime('%Y-%m-%d')
                    scs_do_dia = SolicitacaoCompra.objects.select_for_update().filter(
                        numero__startswith=data_str,
                        sc_mae__isnull=True
                    ).values_list('numero', flat=True)
                    maior_sequencial = 0
                    for num in scs_do_dia:
                        try:
                            sequencial = int(num.split('-')[-1])
                            if sequencial > maior_sequencial:
                                maior_sequencial = sequencial
                        except (ValueError, IndexError):
                            continue
                    proximo_sequencial = maior_sequencial + 1
                    self.numero = f"{data_str}-{proximo_sequencial:03d}"
        super().save(*args, **kwargs)

    @property
    def nome_descritivo(self):
        if not self.numero or not self.data_criacao:
            return "SC em criação..."

        data = timezone.localtime(self.data_criacao)
        semana_do_mes = (data.day - 1) // 7 + 1
        meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        mes_str = meses[data.month - 1]
        ano_str = data.strftime('%Y')
        categoria_nome = self.categoria_sc.nome if self.categoria_sc else "Geral"
        
        # --- LINHA CORRIGIDA ---
        # Adicionamos o self.numero ao final do nome descritivo
        return f"{semana_do_mes}ª semana/{mes_str}/{ano_str} - {categoria_nome} - {self.numero}"

class ItemSolicitacao(models.Model):
    solicitacao = models.ForeignKey(SolicitacaoCompra, on_delete=models.CASCADE, related_name='itens')
    item_catalogo = models.ForeignKey(ItemCatalogo, on_delete=models.PROTECT, null=True, blank=True)
    descricao = models.CharField(max_length=200)
    unidade = models.CharField(max_length=50)
    categoria = models.CharField(max_length=200, blank=True)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    observacoes = models.TextField(blank=True)
    aprovado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.descricao} - {self.quantidade} {self.unidade}"

    class Meta:
        verbose_name = "Item da Solicitação"
        verbose_name_plural = "Itens da Solicitação"

class RequisicaoMaterial(models.Model):
    STATUS_ASSINATURA_CHOICES = [
        ('pendente', 'Pendente de Assinaturas'),
        ('aguardando_diretor', 'Aguardando Diretor'),
        ('assinada', 'Assinada'),
        ('enviada', 'Enviada para Fornecedor'),
    ]
    solicitacao_origem = models.OneToOneField(SolicitacaoCompra, on_delete=models.CASCADE, related_name='requisicao')
    cotacao_vencedora = models.OneToOneField('Cotacao', on_delete=models.CASCADE)
    numero = models.CharField(max_length=20, unique=True, verbose_name="Número RM")
    data_criacao = models.DateTimeField(auto_now_add=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    status_assinatura = models.CharField(max_length=30, choices=STATUS_ASSINATURA_CHOICES, default='pendente')
    assinatura_almoxarife = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rms_assinadas_almoxarife')
    data_assinatura_almoxarife = models.DateTimeField(null=True, blank=True)
    assinatura_diretor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rms_assinadas_diretor')
    data_assinatura_diretor = models.DateTimeField(null=True, blank=True)
    enviada_fornecedor = models.BooleanField(default=False)
    data_envio_fornecedor = models.DateTimeField(null=True, blank=True)

    # --- NOVO CAMPO: ESCOLHA DO CABEÇALHO (CORREÇÃO APLICADA) ---
    header_choice = models.CharField(
        max_length=1, 
        choices=rm_config.HEADER_CHOICES,
        default='A',
        verbose_name="Cabeçalho da RM"
    )
    # -------------------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.numero:
            # Usamos uma transação para garantir que dois usuários peguem o mesmo número ao mesmo tempo
            with transaction.atomic():
                ano = timezone.now().year
                
                # Busca a última RM criada no ano corrente, ordenando pelo número
                ultimo_rm = RequisicaoMaterial.objects.filter(numero__startswith=f'RM-{ano}').order_by('numero').last()
                
                proximo_sequencial = 1
                if ultimo_rm:
                    try:
                        # Extrai o número sequencial do último código (ex: de 'RM-2025-0003', pega o '3')
                        ultimo_sequencial = int(ultimo_rm.numero.split('-')[-1])
                        proximo_sequencial = ultimo_sequencial + 1
                    except (ValueError, IndexError):
                        # Se houver algum erro no formato do número, usa a contagem como um fallback seguro
                        proximo_sequencial = RequisicaoMaterial.objects.filter(numero__startswith=f'RM-{ano}').count() + 1
                
                # Gera o novo número com 4 dígitos (ex: 0001, 0002)
                self.numero = f'RM-{ano}-{proximo_sequencial:04d}'
        
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.numero
        
    class Meta:
        verbose_name = "Requisição de Material (RM)"
        verbose_name_plural = "Requisições de Material (RMs)"

class ItemRecebimento(models.Model):
    requisicao = models.ForeignKey(RequisicaoMaterial, on_delete=models.CASCADE, related_name='itens_recebidos')
    item_original = models.ForeignKey(ItemSolicitacao, on_delete=models.CASCADE)
    quantidade_recebida = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantidade Recebida")
    observacoes = models.TextField(blank=True, verbose_name="Observações do Recebimento")

    def __str__(self):
        return f"{self.requisicao.numero} - {self.item_original.descricao}"

    class Meta:
        verbose_name = "Item de Recebimento"
        verbose_name_plural = "Itens de Recebimento"

class ItemRequisicao(models.Model):
    requisicao = models.ForeignKey(RequisicaoMaterial, on_delete=models.CASCADE, related_name='itens')
    item_solicitacao = models.ForeignKey(ItemSolicitacao, on_delete=models.CASCADE)
    quantidade_recebida = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    data_recebimento = models.DateTimeField(null=True, blank=True)
    documento_fiscal = models.FileField(upload_to='documentos/', null=True, blank=True)
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.item_solicitacao.descricao} - {self.quantidade_recebida}"

    class Meta:
        verbose_name = "Item da Requisição"
        verbose_name_plural = "Itens da Requisição"

def get_nota_fiscal_upload_path(instance, filename):
    return get_recebimento_upload_path(instance, filename, "NF")

def get_sc_assinada_upload_path(instance, filename):
    return get_recebimento_upload_path(instance, filename, "SC-ASSINADA")

def get_boleto_comprovante_upload_path(instance, filename):
    return get_recebimento_upload_path(instance, filename, "BOLETO")

def get_recebimento_upload_path(instance, filename, tipo_documento):
    data_hoje = timezone.now().strftime('%Y-%m-%d')
    sc_numero = str(instance.solicitacao.numero).replace('/', '-')
    rm_numero = "N_A"
    try:
        rm_numero = str(instance.solicitacao.requisicao.numero).replace('/', '-')
    except RequisicaoMaterial.DoesNotExist:
        pass
    nome_base, ext = os.path.splitext(filename)
    novo_nome = f"{tipo_documento}_{sc_numero}_{rm_numero}{ext}"
    identificador_pasta = rm_numero if rm_numero != "N_A" else sc_numero
    return f'recebimentos/{data_hoje}/{identificador_pasta}/{novo_nome}'

class Recebimento(models.Model):
    # ALTERAÇÃO PARA TESTES: models.PROTECT alterado para models.CASCADE
    solicitacao = models.ForeignKey(SolicitacaoCompra, on_delete=models.CASCADE, related_name='recebimentos', verbose_name="Solicitação de Compra")
    recebedor = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Recebedor")
    data_recebimento = models.DateTimeField(default=timezone.now, verbose_name="Data de Recebimento")
    observacoes = models.TextField(blank=True, verbose_name="Observações Gerais")
    
    nota_fiscal = models.FileField(upload_to=get_nota_fiscal_upload_path, verbose_name="Nota Fiscal", blank=True, null=True)
    sc_assinada = models.FileField(upload_to=get_sc_assinada_upload_path, verbose_name="SC Assinada", blank=True, null=True)
    boleto_comprovante = models.FileField(upload_to=get_boleto_comprovante_upload_path, verbose_name="Boleto/Comprovante", blank=True, null=True)

    def __str__(self):
        return f"Recebimento da SC {self.solicitacao.numero} em {self.data_recebimento.strftime('%d/%m/%Y')}"

    class Meta:
        verbose_name = "Recebimento"
        verbose_name_plural = "Recebimentos"
        ordering = ['-data_recebimento']

class ItemRecebido(models.Model):
    recebimento = models.ForeignKey(Recebimento, on_delete=models.CASCADE, related_name='itens_recebidos')
    # ALTERAÇÃO PARA TESTES: models.PROTECT alterado para models.CASCADE
    item_solicitado = models.ForeignKey(ItemSolicitacao, on_delete=models.CASCADE, related_name='recebimentos')
    quantidade_recebida = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantidade Recebida")
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.quantidade_recebida} x {self.item_solicitado.descricao}"

    class Meta:
        verbose_name = "Item Recebido"
        verbose_name_plural = "Itens Recebidos"

class Cotacao(models.Model):
    solicitacao = models.ForeignKey(SolicitacaoCompra, on_delete=models.CASCADE, related_name='cotacoes')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    data_cotacao = models.DateTimeField(auto_now_add=True, verbose_name="Data da Cotação")
    prazo_entrega = models.CharField(max_length=100, blank=True, verbose_name="Prazo de Entrega")
    condicao_pagamento = models.CharField(max_length=100, blank=True, verbose_name="Condição de Pagamento")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    vencedora = models.BooleanField(default=False, verbose_name="Cotação Vencedora")
    valor_frete = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor do Frete")
    endereco_entrega = models.ForeignKey(DestinoEntrega, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Endereço de Entrega")

    @property
    def valor_total(self):
        from django.db.models import Sum, F
        total_itens = self.itens_cotados.aggregate(
            total=Sum(F('preco') * F('item_solicitacao__quantidade'))
        )['total'] or 0
        return total_itens + self.valor_frete

    class Meta:
        verbose_name = "Cotação"
        verbose_name_plural = "Cotações"

    def __str__(self):
        return f"Cotação {self.id} de {self.fornecedor.nome_fantasia} para SC {self.solicitacao.numero}"

    
class ItemCotacao(models.Model):
    cotacao = models.ForeignKey(Cotacao, on_delete=models.CASCADE, related_name='itens_cotados')
    item_solicitacao = models.ForeignKey(ItemSolicitacao, on_delete=models.CASCADE, related_name='itens_cotados')
    preco = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço do Item")
    selecionado = models.BooleanField(default=False, verbose_name="Item Vencedor")

    def __str__(self):
        return f"{self.item_solicitacao.descricao} - R$ {self.preco}"

class HistoricoSolicitacao(models.Model):
    solicitacao = models.ForeignKey(SolicitacaoCompra, on_delete=models.CASCADE, related_name='historico')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    acao = models.CharField(max_length=255)
    detalhes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.solicitacao.numero} - {self.acao}"

    class Meta:
        ordering = ['timestamp']

class EnvioCotacao(models.Model):
    FORMAS_PAGAMENTO = [
        ('avista', 'À Vista'),
        ('pix', 'Pix'),
        ('boleto', 'Boleto Bancário'),
        ('cartao_credito', 'Cartão de Crédito'),
        ('cartao_debito', 'Cartão de Débito'),
        ('transferencia', 'Transferência Bancária'),
        ('a_negociar', 'A Negociar'),
    ]

    solicitacao = models.ForeignKey(SolicitacaoCompra, on_delete=models.CASCADE, related_name='envios_cotacao')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name='cotacoes_enviadas')
    itens = models.ManyToManyField(ItemSolicitacao, related_name='envios')
    data_envio = models.DateTimeField(auto_now_add=True)
    prazo_resposta = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[('aguardando', 'Aguardando Resposta'), ('respondido', 'Respondido')], default='aguardando')
    # --- CAMPOS ADICIONADOS ---
    forma_pagamento = models.CharField(max_length=20, choices=FORMAS_PAGAMENTO, default='a_negociar', verbose_name="Forma de Pagamento Sugerida")
    prazo_pagamento = models.PositiveIntegerField(default=0, verbose_name="Prazo de Pagamento (dias)", help_text="Prazo de pagamento sugerido ao fornecedor em dias.")

    def __str__(self):
        return f"Envio para {self.fornecedor.nome_fantasia} - SC {self.solicitacao.numero}"
        
    class Meta:
        verbose_name = "Envio de Cotação"
        verbose_name_plural = "Envios de Cotação"