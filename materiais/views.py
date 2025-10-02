from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q, Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.views.decorators.csrf import csrf_exempt
from difflib import SequenceMatcher
from .forms import SolicitacaoCompraForm
from .models import (
    User, SolicitacaoCompra, ItemSolicitacao, Fornecedor, ItemCatalogo, 
    Obra, Cotacao, RequisicaoMaterial, HistoricoSolicitacao, 
    ItemCotacao, CategoriaSC, EnvioCotacao, CategoriaItem, Tag, UnidadeMedida, DestinoEntrega,
    Recebimento, ItemRecebido # <-- NOVOS MODELOS PRESENTES
)
import json # Adicione esta importação no topo do seu arquivo views.py
from django.db import transaction
from django.urls import reverse

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from . import rm_config


#solicitacao = SolicitacaoCompra.objects.create(...)cadastrar_itens
def similaridade_texto(a, b):  
    """Calcula similaridade entre dois textos (0 a 1)"""  
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('materiais:dashboard')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    return render(request, 'materiais/login.html')


def logout_view(request):
    logout(request)
    return redirect('materiais:login')


@login_required
def dashboard(request):
    perfil = request.user.perfil
    user_obras = request.user.obras.all()
    
    # Lógica de busca já inclui o 'diretor'
    if perfil in ['almoxarife_escritorio', 'diretor']:
        base_query = SolicitacaoCompra.objects.all()
    elif perfil in ['engenheiro', 'almoxarife_obra']:
        if user_obras.exists():
            base_query = SolicitacaoCompra.objects.filter(obra__in=user_obras)
        else:
            base_query = SolicitacaoCompra.objects.none()
    else:
        base_query = SolicitacaoCompra.objects.none()

    aprovado_statuses = ['aprovada', 'aprovado_engenharia']
    cotacao_statuses = ['em_cotacao', 'aguardando_resposta', 'cotacao_selecionada']
    
    context = {
        'em_aberto': base_query.filter(status='pendente_aprovacao').count(),
        'aprovado': base_query.filter(status__in=aprovado_statuses).count(),
        'em_cotacao': base_query.filter(status__in=cotacao_statuses).count(),
        'requisicoes': base_query.filter(status='finalizada').count(),
        'a_caminho': base_query.filter(status='a_caminho').count(),
        'entregue': base_query.filter(status='recebida').count(),
    }

    if perfil == 'almoxarife_obra':
        return render(request, 'materiais/dashboard_almoxarife_obra.html', context)
    elif perfil == 'engenheiro':
        return render(request, 'materiais/dashboard_engenheiro.html', context)
    elif perfil == 'almoxarife_escritorio':
        return render(request, 'materiais/dashboard_almoxarife_escritorio.html', context)
    elif perfil == 'diretor':
        return render(request, 'materiais/dashboard_diretor.html', context)
    else:
        return render(request, 'materiais/dashboard.html')
    
# TRECHO COMPLETO E CORRIGIDO A SER COLOCADO NO LUGAR (EM views.py)

@login_required
def lista_solicitacoes(request):
    status_filtrado = request.GET.get('status', None)
    user = request.user
    
    # 1. Define uma query base EXATAMENTE como no dashboard, garantindo consistência
    if user.perfil in ['almoxarife_escritorio', 'diretor']:
        base_query = SolicitacaoCompra.objects.all()
    
    elif user.perfil in ['almoxarife_obra', 'engenheiro']:
        user_obras = user.obras.all()
        if user_obras.exists():
            base_query = SolicitacaoCompra.objects.filter(obra__in=user_obras)
        else:
            base_query = SolicitacaoCompra.objects.none() # Se não tem obra, não vê nada
            
    else:
        # Para perfis não definidos, não retorna nada por segurança
        base_query = SolicitacaoCompra.objects.none()

    # 2. Aplica o filtro de status (se houver) na query base
    solicitacoes = base_query
    if status_filtrado and status_filtrado in [s[0] for s in SolicitacaoCompra.STATUS_CHOICES]:
        
        # Lógica especial para o status 'aprovada' do card
        if status_filtrado == 'aprovada':
            aprovado_statuses = ['aprovada', 'aprovado_engenharia']
            solicitacoes = solicitacoes.filter(status__in=aprovado_statuses)
        
        # Lógica especial para o status 'em_cotacao' do card
        elif status_filtrado == 'em_cotacao':
            cotacao_statuses = ['em_cotacao', 'aguardando_resposta', 'cotacao_selecionada']
            solicitacoes = solicitacoes.filter(status__in=cotacao_statuses)
            
        else:
            solicitacoes = solicitacoes.filter(status=status_filtrado)

    # 3. Monta o contexto final para o template
    context = {
        'solicitacoes': solicitacoes.select_related('obra').order_by('-data_criacao'),
        'status_filtrado': status_filtrado,
        'status_choices': dict(SolicitacaoCompra.STATUS_CHOICES)
    }
    return render(request, 'materiais/lista_solicitacoes.html', context)


@login_required
def minhas_solicitacoes(request):
    # Pega os valores dos filtros da URL (GET)
    termo_busca = request.GET.get('q', '').strip()
    ano = request.GET.get('ano', '')
    mes = request.GET.get('mes', '')
    categoria_id = request.GET.get('categoria', '')

    # 1. Query base: filtra APENAS as solicitações do usuário logado
    base_query = SolicitacaoCompra.objects.filter(
        solicitante=request.user
    ).select_related('obra', 'categoria_sc').prefetch_related('itens').order_by('-data_criacao')

    # 2. Aplica os filtros adicionais, se existirem
    solicitacoes = base_query
    if termo_busca:
        solicitacoes = solicitacoes.filter(
            Q(numero__icontains=termo_busca) |
            Q(justificativa__icontains=termo_busca) |
            Q(itens__descricao__icontains=termo_busca) |
            Q(obra__nome__icontains=termo_busca)
        ).distinct()
    
    if ano:
        solicitacoes = solicitacoes.filter(data_criacao__year=ano)
    
    if mes:
        solicitacoes = solicitacoes.filter(data_criacao__month=mes)
        
    if categoria_id:
        solicitacoes = solicitacoes.filter(categoria_sc_id=categoria_id)

    # 3. Prepara o contexto para enviar ao template
    context = {
        'solicitacoes': solicitacoes,
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'meses_opcoes': range(1, 13), # <-- ADICIONE ESTA LINHA
        # Devolve os valores dos filtros para manter os campos preenchidos
        'filtros_aplicados': {
            'q': termo_busca,
            'ano': ano,
            'mes': mes,
            'categoria': categoria_id,
        }
    }
    
    return render(request, 'materiais/minhas_solicitacoes.html', context)
# Lembre-se de ter essas importações no topo do seu views.py


@login_required
def nova_solicitacao(request):
    if request.method == 'POST':
        try:
            obra_id = request.POST.get('obra')
            data_necessidade = request.POST.get('data_necessidade')
            justificativa = request.POST.get('justificativa')
            is_emergencial = request.POST.get('is_emergencial') == 'on'
            categoria_sc_id = request.POST.get('categoria_sc')
            destino_id = request.POST.get('destino') # Captura o novo campo
            
            itens_json = request.POST.get('itens_json', '[]')
            itens_data = json.loads(itens_json)

            if not all([obra_id, data_necessidade, itens_data]):
                messages.error(request, 'Erro: Obra, data de necessidade e ao menos um item são obrigatórios.')
                return redirect('materiais:nova_solicitacao')

            obra = get_object_or_404(Obra, id=obra_id)
            status_inicial = 'aprovada' if request.user.perfil in ['engenheiro', 'almoxarife_escritorio', 'diretor'] else 'pendente_aprovacao'

            with transaction.atomic():
                solicitacao = SolicitacaoCompra.objects.create(
                    solicitante=request.user, obra=obra, data_necessidade=data_necessidade,
                    justificativa=justificativa, is_emergencial=is_emergencial,
                    status=status_inicial, categoria_sc_id=categoria_sc_id,
                    destino_id=destino_id if destino_id else None # Salva o novo campo
                )
                HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="Solicitação Criada")

                for item_data in itens_data:
                    item_catalogo = get_object_or_404(ItemCatalogo, id=item_data.get('item_id'))
                    ItemSolicitacao.objects.create(
                        solicitacao=solicitacao,
                        item_catalogo=item_catalogo,
                        descricao=item_catalogo.descricao,
                        unidade=item_catalogo.unidade.sigla,
                        categoria=str(item_catalogo.categoria),
                        quantidade=float(item_data.get('quantidade')),
                        observacoes=item_data.get('observacao')
                    )
                
                if request.user.perfil in ['engenheiro', 'almoxarife_escritorio']:
                    solicitacao.aprovador = request.user
                    solicitacao.data_aprovacao = timezone.now()
                    solicitacao.save()
                    HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="Aprovada na Criação")
                
                messages.success(request, f'Solicitação {solicitacao.numero} criada com sucesso!')
                return redirect('materiais:lista_solicitacoes')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao processar sua solicitação: {e}')
            return redirect('materiais:nova_solicitacao')

    if request.user.perfil == 'almoxarife_escritorio':
        obras = Obra.objects.filter(ativa=True).order_by('nome')
    else:
        obras = request.user.obras.filter(ativa=True).order_by('nome')
    
    context = {
        'obras': obras,
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'destinos_entrega': DestinoEntrega.objects.all().order_by('nome'),
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome'),
    }
    
    return render(request, 'materiais/nova_solicitacao.html', context)
#solicitacao.save()
@login_required
def lista_fornecedores(request):
    return render(request, 'materiais/lista_fornecedores.html')


@login_required
def analisar_solicitacoes(request):
    if request.user.perfil != 'engenheiro':
        messages.error(request, 'Acesso negado. Apenas engenheiros podem analisar solicitações.')
        return redirect('materiais:dashboard')

    solicitacoes_pendentes = SolicitacaoCompra.objects.filter(
        status='pendente_aprovacao'
    ).order_by('-data_criacao')

    return render(request, 'materiais/analisar_solicitacoes.html', {
        'solicitacoes_pendentes': solicitacoes_pendentes
    })


@login_required
def aprovar_solicitacao(request, solicitacao_id):
    if request.user.perfil != 'engenheiro':
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    if solicitacao.status != 'pendente_aprovacao':
        return JsonResponse({'success': False, 'message': 'Solicitação não pode ser aprovada'})
    
    # --- MUDANÇA PARA O NOVO STATUS ---
    solicitacao.status = 'aprovado_engenharia'
    solicitacao.aprovador = request.user
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.save()
    
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="Aprovada pelo Engenheiro",
        detalhes="Todos os itens foram aprovados."
    )
    
    messages.success(request, f'Solicitação {solicitacao.numero} aprovada com sucesso!')
    return JsonResponse({'success': True, 'message': 'Solicitação aprovada!'})

@login_required
def rejeitar_solicitacao(request, solicitacao_id):
    if request.user.perfil != 'engenheiro':
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    if solicitacao.status != 'pendente_aprovacao':
        return JsonResponse({'success': False, 'message': 'Solicitação não pode ser rejeitada'})
    
    solicitacao.status = 'rejeitada'
    solicitacao.aprovador = request.user
    solicitacao.data_aprovacao = timezone.now()
    
    observacoes = request.POST.get('observacoes', 'Rejeitada pelo engenheiro')
    solicitacao.observacoes_aprovacao = observacoes
    solicitacao.save()
    
    # --- REGISTRO DE HISTÓRICO ---
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="Solicitação Rejeitada",
        detalhes=observacoes
    )
    # --- FIM DO REGISTRO ---
    
    messages.success(request, f'Solicitação {solicitacao.numero} rejeitada!')
    return JsonResponse({'success': True, 'message': 'Solicitação rejeitada!'})

    
@login_required
def editar_solicitacao(request, solicitacao_id):
    # View placeholder para a futura tela de edição.
    # No momento, ela apenas exibe uma mensagem e redireciona.
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    messages.info(request, f'A funcionalidade "Editar" para a SC {solicitacao.numero} está em desenvolvimento.')
    
    # Redireciona de volta para a página mais relevante
    if request.user.perfil == 'almoxarife_escritorio':
        return redirect('materiais:gerenciar_cotacoes')
    
@login_required
def marcar_em_cotacao(request, solicitacao_id):
    # CORREÇÃO: Adicionado 'diretor' à verificação de perfil
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    status_permitidos = ['aprovada', 'aprovado_engenharia']
    if solicitacao.status not in status_permitidos:
        messages.error(request, 'Esta solicitação não está em um status válido para iniciar a cotação.')
        return redirect('materiais:gerenciar_cotacoes')

    solicitacao.status = 'em_cotacao'
    solicitacao.save()
    
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="Início da Cotação",
        detalhes="Processo de cotação com fornecedores iniciado."
    )

    messages.success(request, f'O processo de cotação para a SC "{solicitacao.nome_descritivo}" foi iniciado!')
    
    return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=em-cotacao")

@login_required
def iniciar_cotacao(request, solicitacao_id, fornecedor_id=None):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
        
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    fornecedor_selecionado = get_object_or_404(Fornecedor, id=fornecedor_id)
    # Pega o envio original para buscar os dados de pagamento
    envio_original = EnvioCotacao.objects.filter(solicitacao=solicitacao, fornecedor=fornecedor_selecionado).first()

    if request.method == 'POST':
        # --- CAPTURANDO NOVOS CAMPOS ---
        prazo_entrega = request.POST.get('prazo_entrega')
        condicao_pagamento = request.POST.get('condicao_pagamento')
        observacoes = request.POST.get('observacoes')
        valor_frete_str = request.POST.get('valor_frete', '0').replace('.', '').replace(',', '.')
        endereco_entrega_id = request.POST.get('endereco_entrega')

        with transaction.atomic():
            nova_cotacao, created = Cotacao.objects.update_or_create(
                solicitacao=solicitacao, 
                fornecedor=fornecedor_selecionado, 
                defaults={
                    'prazo_entrega': prazo_entrega,
                    'condicao_pagamento': condicao_pagamento, 
                    'observacoes': observacoes,
                    # --- SALVANDO NOVOS CAMPOS ---
                    'valor_frete': float(valor_frete_str) if valor_frete_str else 0.0,
                    'endereco_entrega_id': endereco_entrega_id if endereco_entrega_id else None
                }
            )

            nova_cotacao.itens_cotados.all().delete()
            
            itens_cotados_count = 0
            for item_solicitado in envio_original.itens.all():
                preco_str = request.POST.get(f'preco_{item_solicitado.id}')
                if preco_str:
                    preco_limpo = preco_str.replace('R$', '').strip().replace('.', '').replace(',', '.')
                    try:
                        preco_val = float(preco_limpo)
                        if preco_val > 0:
                            ItemCotacao.objects.create(cotacao=nova_cotacao, item_solicitacao=item_solicitado, preco=preco_val)
                            itens_cotados_count += 1
                    except (ValueError, TypeError): continue
            
            if itens_cotados_count == 0:
                nova_cotacao.delete()
                messages.error(request, "Nenhum preço válido foi informado. A cotação não foi registrada.")
            else:
                total_enviado = solicitacao.envios_cotacao.count()
                total_recebido = solicitacao.cotacoes.count()
                
                historico_detalhes = f"Preços do fornecedor {fornecedor_selecionado.nome_fantasia} foram registrados."
                if total_enviado > 0 and total_enviado == total_recebido:
                    solicitacao.status = 'cotacao_selecionada'
                    solicitacao.save()
                    historico_detalhes += " Todas as cotações solicitadas foram recebidas. SC movida para análise."
                
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao, usuario=request.user, acao="Cotação Registrada",
                    detalhes=historico_detalhes
                )
                messages.success(request, f"Cotação para {fornecedor_selecionado.nome_fantasia} registrada com sucesso!")
                return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=recebidas")

    context = {
        'solicitacao': solicitacao,
        'fornecedor_selecionado': fornecedor_selecionado,
        'envio_cotacao': envio_original,
        'itens_para_cotar': envio_original.itens.all() if envio_original else [],
        'destinos_entrega': DestinoEntrega.objects.all().order_by('nome')
    }
    return render(request, 'materiais/iniciar_cotacao.html', context)

@login_required
def selecionar_cotacao_vencedora(request, cotacao_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
        
    if request.method == 'POST':
        cotacao_vencedora = get_object_or_404(Cotacao, id=cotacao_id)
        solicitacao = cotacao_vencedora.solicitacao

        # --- INÍCIO DA CORREÇÃO DE SEGURANÇA ---
        # ANTES de fazer qualquer coisa, verifica se uma RM já não foi criada para esta SC.
        # O 'hasattr(solicitacao, 'requisicao')' checa se a relação OneToOne já existe.
        if hasattr(solicitacao, 'requisicao'):
            messages.warning(request, f'A Requisição de Material para a SC {solicitacao.numero} já foi gerada anteriormente.')
            return redirect('materiais:gerenciar_requisicoes')
        # --- FIM DA CORREÇÃO DE SEGURANÇA ---

        with transaction.atomic():
            # Apaga as outras cotações e envios que não foram vencedores
            solicitacao.cotacoes.exclude(pk=cotacao_vencedora.pk).delete()
            solicitacao.envios_cotacao.all().delete()
            
            # Marca a cotação como vencedora
            cotacao_vencedora.vencedora = True
            cotacao_vencedora.save()

            # Agora, cria a nova RM com segurança
            nova_rm = RequisicaoMaterial.objects.create(
                solicitacao_origem=solicitacao,
                cotacao_vencedora=cotacao_vencedora,
                valor_total=cotacao_vencedora.valor_total,
                status_assinatura='pendente' 
            )

            # Atualiza o status da SC para finalizada
            solicitacao.status = 'finalizada'
            solicitacao.save()
            
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao, usuario=request.user, acao="RM Gerada",
                detalhes=f"Cotação de {cotacao_vencedora.fornecedor.nome_fantasia} selecionada. RM {nova_rm.numero} criada."
            )
            messages.success(request, f"Cotação selecionada! RM {nova_rm.numero} foi gerada e está pendente de assinaturas.")
    
    return redirect('materiais:gerenciar_requisicoes')

@login_required
def rejeitar_cotacao(request, cotacao_id):
    if request.method == 'POST':
        cotacao = get_object_or_404(Cotacao, id=cotacao_id)
        solicitacao = cotacao.solicitacao # Capturamos a SC antes de apagar a cotação
        fornecedor_nome = cotacao.fornecedor.nome_fantasia

        # Apaga a cotação
        cotacao.delete()

        historico_detalhes = f"A cotação do fornecedor {fornecedor_nome} foi rejeitada e removida."
        
        # --- NOVA LÓGICA DE VERIFICAÇÃO DE STATUS ---
        # Verifica se a SC ficou sem nenhuma outra cotação registrada
        if not solicitacao.cotacoes.exists():
            # Se não houver mais cotações, reverte o status para aguardar novas cotações
            solicitacao.status = 'aguardando_resposta'
            solicitacao.save()
            historico_detalhes += " A SC retornou ao estado 'Aguardando Resposta' pois não há outras cotações."

        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            acao="Cotação Rejeitada",
            detalhes=historico_detalhes
        )

        messages.warning(request, f"A cotação do fornecedor {fornecedor_nome} foi rejeitada.")
        
        # Redireciona para a aba correta dependendo do que aconteceu
        if solicitacao.status == 'aguardando_resposta':
             return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=aguardando")
        else:
            return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=recebidas")

    return redirect('materiais:gerenciar_cotacoes')

'''@login_required
def receber_material(request):
    if request.user.perfil != 'almoxarife_obra':
        messages.error(request, 'Acesso negado. Apenas almoxarife da obra pode receber materiais.')
        return redirect('materiais:dashboard')

    scs_finalizadas = SolicitacaoCompra.objects.filter(
        status='finalizada'
    ).select_related('obra', 'solicitante').prefetch_related('itens').order_by('-data_criacao')

    return render(request, 'materiais/receber_material.html', {
        'scs_finalizadas': scs_finalizadas
    })'''


'''@login_required
def iniciar_recebimento(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_obra':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='finalizada')

    if request.method == 'POST':
        from django.db import transaction
        
        with transaction.atomic():
            ultimo_rm = RequisicaoMaterial.objects.order_by('-id').first()
            if ultimo_rm:
                numero_rm = f"RM-{str(ultimo_rm.id + 1).zfill(3)}"
            else:
                numero_rm = "RM-001"
            
            rm = RequisicaoMaterial.objects.create(
                numero=numero_rm,
                solicitacao_origem=solicitacao,
                recebedor=request.user,
                data_recebimento=timezone.now().date(),
                observacoes=request.POST.get('observacoes_gerais', '')
            )
            
            quantidades_recebidas = request.POST.getlist('quantidade_recebida[]')
            observacoes_recebimento = request.POST.getlist('observacoes_recebimento[]')
            itens_processados = 0

            for i, item in enumerate(solicitacao.itens.all()):
                if i < len(quantidades_recebidas) and quantidades_recebidas[i]:
                    quantidade_recebida = float(quantidades_recebidas[i])
                    if quantidade_recebida > 0:
                        ItemRecebimento.objects.create(
                            requisicao=rm,
                            item_original=item,
                            quantidade_recebida=quantidade_recebida,
                            observacoes=observacoes_recebimento[i] if i < len(observacoes_recebimento) else ''
                        )
                        itens_processados += 1
            
            if itens_processados > 0:
                solicitacao.status = 'recebida'
                solicitacao.recebedor = request.user
                solicitacao.data_recebimento = timezone.now()
                solicitacao.save()
                
                # --- REGISTRO DE HISTÓRICO ---
                # Este bloco está corretamente indentado dentro do "if"
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao,
                    usuario=request.user,
                    acao="Material Recebido",
                    detalhes=f"Recebimento parcial/total registrado na RM {rm.numero}."
                )
                # --- FIM DO REGISTRO ---
                
                messages.success(request, f'✅ Material recebido com sucesso! RM {numero_rm} criada.')
                return redirect('materiais:receber_material')
            else:
                rm.delete()
                messages.error(request, 'Informe pelo menos um item recebido.')

    return render(request, 'materiais/iniciar_recebimento.html', {
        'solicitacao': solicitacao
    })'''




@login_required
def historico_recebimentos(request):
    if request.user.perfil != 'almoxarife_obra':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    # CORREÇÃO: Busca os novos objetos 'Recebimento' criados pelo usuário logado
    recebimentos_feitos = Recebimento.objects.filter(
        recebedor=request.user
    ).select_related('solicitacao__obra').prefetch_related('itens_recebidos').order_by('-data_recebimento')

    context = {
        # O nome da variável no template ('materiais_recebidos') foi mantido para não quebrar o HTML
        'materiais_recebidos': recebimentos_feitos
    }
    return render(request, 'materiais/historico_recebimentos.html', context)


@login_required
def cadastrar_itens(request):
    # PERMISSÃO CORRIGIDA PARA INCLUIR O DIRETOR
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado. Apenas o escritório ou diretoria pode cadastrar itens.')
        return redirect('materiais:dashboard')

    categorias_principais_list = CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome')
    unidades_list = UnidadeMedida.objects.all().order_by('nome')
    tags_list = Tag.objects.all().order_by('nome')

    if request.method == 'POST':
        subcategoria_id = request.POST.get('subcategoria')
        descricao = request.POST.get('descricao')
        unidade_id = request.POST.get('unidade')
        tags_ids = request.POST.getlist('tags')
        status_ativo = request.POST.get('status') == 'on'
        forcar_cadastro = request.POST.get('forcar_cadastro') == 'true'
        
        erros = []
        if not descricao:
            erros.append("O campo 'Descrição do Item' é obrigatório.")
        if not request.POST.get('categoria'):
            erros.append("O campo 'Categoria' é obrigatório.")
        if not subcategoria_id:
            erros.append("O campo 'Subcategoria' é obrigatório.")
        if not unidade_id:
            erros.append("O campo 'Unidade de Medida' é obrigatório.")

        contexto_erro = {
            'itens': ItemCatalogo.objects.select_related('categoria', 'unidade').order_by('-id'),
            'categorias_principais': categorias_principais_list,
            'unidades': unidades_list,
            'tags': tags_list,
            'form_data': request.POST
        }
        
        if erros:
            for erro in erros:
                messages.error(request, erro)
            return render(request, 'materiais/cadastrar_itens.html', contexto_erro)
        
        if ItemCatalogo.objects.filter(descricao__iexact=descricao).exists():
            messages.error(request, f'❌ Já existe um item com a descrição "{descricao}"!')
            return render(request, 'materiais/cadastrar_itens.html', contexto_erro)
        
        if not forcar_cadastro:
            itens_similares = []
            for item_existente in ItemCatalogo.objects.only('codigo', 'descricao'):
                similaridade = similaridade_texto(descricao, item_existente.descricao)
                if similaridade >= 0.7:
                    itens_similares.append({
                        'item': item_existente,
                        'similaridade': round(similaridade * 100, 1)
                    })
            
            if itens_similares:
                contexto_erro['itens_similares'] = itens_similares
                contexto_erro['mostrar_confirmacao'] = True
                return render(request, 'materiais/cadastrar_itens.html', contexto_erro)
        
        try:
            categoria_final_obj = get_object_or_404(CategoriaItem, id=subcategoria_id)
            unidade_obj = get_object_or_404(UnidadeMedida, id=unidade_id)

            novo_item = ItemCatalogo(
                descricao=descricao,
                categoria=categoria_final_obj,
                unidade=unidade_obj,
                ativo=status_ativo
            )
            novo_item.save()
            
            if tags_ids:
                novo_item.tags.set(tags_ids)

            messages.success(request, f'✅ Item "{novo_item.descricao}" (Código: {novo_item.codigo}) cadastrado com sucesso!')
            return redirect('materiais:cadastrar_itens')
        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao salvar o item: {e}')
            return render(request, 'materiais/cadastrar_itens.html', contexto_erro)

    context = {
        'itens': ItemCatalogo.objects.select_related('categoria', 'unidade').order_by('-id'),
        'categorias_principais': categorias_principais_list,
        'unidades': unidades_list,
        'tags': tags_list
    }
    return render(request, 'materiais/cadastrar_itens.html', context)

@login_required
def cadastrar_obras(request):
    # PERMISSÃO CORRIGIDA PARA INCLUIR O DIRETOR
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado. Apenas o escritório ou diretoria pode cadastrar obras.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        nome = request.POST.get('nome')
        endereco = request.POST.get('endereco')
        
        if nome:
            Obra.objects.create(
                nome=nome,
                endereco=endereco or ''
            )
            messages.success(request, f'Obra {nome} cadastrada com sucesso!')
            return redirect('materiais:cadastrar_obras')

    obras = Obra.objects.all().order_by('nome')
    return render(request, 'materiais/cadastrar_obras.html', {
        'obras': obras
    })


@login_required
def gerenciar_fornecedores(request):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        cnpj = request.POST.get('cnpj')
        
        # --- CORREÇÃO CRÍTICA DO VALUERROR ---
        produtos_ids_string = request.POST.get('produtos_fornecidos', '')
        # Garante que seja uma lista de IDs válidos (strings ou vazia)
        produtos_ids = [pid.strip() for pid in produtos_ids_string.split(',') if pid.strip()]
        # --- FIM DA CORREÇÃO CRÍTICA DO VALUERROR ---
        
        if Fornecedor.objects.filter(cnpj=cnpj).exists():
            messages.error(request, f'❌ CNPJ {cnpj} já cadastrado!')
        else:
            try:
                # O restante da lógica de criação de fornecedor
                novo_fornecedor = Fornecedor.objects.create(
                    nome_fantasia=request.POST.get('nome_fantasia'),
                    razao_social=request.POST.get('razao_social'),
                    cnpj=cnpj,
                    tipo=request.POST.get('tipo'),
                    email=request.POST.get('email'),
                    contato_nome=request.POST.get('contato_nome'),
                    contato_telefone=request.POST.get('contato_telefone'),
                    contato_whatsapp=request.POST.get('contato_whatsapp'),
                    cep=request.POST.get('cep'),
                    logradouro=request.POST.get('logradouro'),
                    numero=request.POST.get('numero'),
                    bairro=request.POST.get('bairro'),
                    cidade=request.POST.get('cidade'),
                    estado=request.POST.get('estado'),
                    ativo=True
                )
                
                # Associa as categorias/subcategorias
                if produtos_ids:
                    novo_fornecedor.produtos_fornecidos.set(produtos_ids)
                else:
                    # Se a lista estiver vazia, .clear() evita o ValueError e desvincula.
                    novo_fornecedor.produtos_fornecidos.clear()

                messages.success(request, f'✅ Fornecedor {novo_fornecedor.nome_fantasia} cadastrado com sucesso!')
                return redirect('materiais:gerenciar_fornecedores')
            except Exception as e:
                messages.error(request, f'Ocorreu um erro ao cadastrar: {e}')


    context = {
        'fornecedores': Fornecedor.objects.all().order_by('nome_fantasia'),
        # Passando as categorias principais para o template (necessário para a cascata)
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome')
    }
    return render(request, 'materiais/gerenciar_fornecedores.html', context)



@login_required
def finalizar_compra(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_escritorio':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='cotacao_selecionada')
    cotacao_selecionada = solicitacao.cotacoes.filter(selecionada=True).first()

    if request.method == 'POST':
        observacoes_finalizacao = request.POST.get('observacoes_finalizacao', '')
        
        solicitacao.status = 'finalizada'
        # As observações da finalização podem ser salvas em um campo apropriado se desejar
        # solicitacao.observacoes_aprovacao = observacoes_finalizacao
        solicitacao.save()

        # --- REGISTRO DE HISTÓRICO ---
        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            acao="Compra Finalizada",
            detalhes=f"Pedido de compra efetuado com o fornecedor {cotacao_selecionada.fornecedor.nome}. Observações: {observacoes_finalizacao}"
        )
        # --- FIM DO REGISTRO ---
        
        messages.success(request, f'✅ Compra da SC {solicitacao.numero} finalizada com sucesso!')
        return redirect('materiais:gerenciar_cotacoes') # Melhor redirecionar para a lista de cotações

    return render(request, 'materiais/finalizar_compra.html', {
        'solicitacao': solicitacao,
        'cotacao_selecionada': cotacao_selecionada
    })

@login_required
def selecionar_item_cotado(request, item_cotado_id):
    if request.method == 'POST' and request.user.perfil == 'almoxarife_escritorio':
        item_vencedor = get_object_or_404(ItemCotacao, id=item_cotado_id)
        item_solicitado_original = item_vencedor.item_solicitacao

        # Garante que estamos trabalhando com a solicitação de compra correta
        solicitacao_principal = item_solicitado_original.solicitacao

        with transaction.atomic():
            # Desmarca qualquer outro item vencedor para esta mesma solicitação de item
            item_solicitado_original.itens_cotados.update(selecionado=False)
            
            # Marca o item selecionado como vencedor
            item_vencedor.selecionado = True
            item_vencedor.save()
            
            # Atualiza status da solicitação principal para 'Cotação Selecionada'
            # Isso indica que pelo menos um item já tem um vencedor.
            if solicitacao_principal.status != 'cotacao_selecionada':
                solicitacao_principal.status = 'cotacao_selecionada'
                solicitacao_principal.save()

            # Adiciona ao histórico
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao_principal,
                usuario=request.user,
                acao="Item de Cotação Selecionado",
                detalhes=f"Item '{item_solicitado_original.descricao}' do fornecedor '{item_vencedor.cotacao.fornecedor.nome}' foi selecionado como vencedor."
            )

        messages.success(request, f"Item '{item_solicitado_original.descricao}' do fornecedor '{item_vencedor.cotacao.fornecedor.nome}' selecionado!")

    # Redireciona de volta para a tela de gerenciamento, focando na aba correta.
    return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=recebidas")


@login_required
def api_solicitacao_itens(request, solicitacao_id):
    """API para buscar itens de uma solicitação (usado na aprovação parcial e na cotação)"""
    # PERMISSÃO CORRIGIDA PARA INCLUIR O DIRETOR
    if request.user.perfil not in ['engenheiro', 'almoxarife_escritorio', 'diretor']:
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    try:
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        
        itens_data = []
        for item in solicitacao.itens.all():
            itens_data.append({
                'id': item.id,
                'descricao': item.descricao,
                'quantidade': float(item.quantidade),
                'unidade': item.unidade,
                'observacoes': item.observacoes or ''
            })
        
        return JsonResponse({
            'success': True,
            'itens': itens_data,
            'solicitacao': {
                'id': solicitacao.id,
                'numero': solicitacao.numero,
                'obra': solicitacao.obra.nome,
                'solicitante': solicitacao.solicitante.get_full_name() or solicitacao.solicitante.username
            }
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def aprovar_parcial(request, solicitacao_id):
    """Função para aprovação parcial de solicitações"""
    if request.user.perfil != 'engenheiro':
        return JsonResponse({'success': False, 'message': 'Acesso negado'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método não permitido'})
    
    try:
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        
        if solicitacao.status != 'pendente_aprovacao':
            return JsonResponse({'success': False, 'message': 'Solicitação não pode ser aprovada parcialmente'})
        
        itens_aprovados_ids = request.POST.getlist('itens_aprovados[]')
        observacoes = request.POST.get('observacoes', '')
        
        if not itens_aprovados_ids:
            return JsonResponse({'success': False, 'message': 'Selecione pelo menos um item para aprovar'})
        
        from django.db import transaction
        
        with transaction.atomic():
            # Cria a nova solicitação com os itens aprovados
            nova_solicitacao = SolicitacaoCompra.objects.create(
                solicitante=solicitacao.solicitante,
                obra=solicitacao.obra,
                data_necessidade=solicitacao.data_necessidade,
                justificativa=f"Aprovação parcial da SC {solicitacao.numero}",
                status='aprovada',
                aprovador=request.user,
                data_aprovacao=timezone.now(),
                observacoes_aprovacao=observacoes
            )
            
            # Move os itens da solicitação original para a nova
            itens_aprovados = ItemSolicitacao.objects.filter(id__in=itens_aprovados_ids, solicitacao=solicitacao)
            for item_original in itens_aprovados:
                ItemSolicitacao.objects.create(
                    solicitacao=nova_solicitacao,
                    descricao=item_original.descricao,
                    quantidade=item_original.quantidade,
                    unidade=item_original.unidade,
                    observacoes=item_original.observacoes
                )
            
            # Remove os itens movidos da solicitação original
            itens_aprovados.delete()
            
            # --- REGISTRO DE HISTÓRICO ---
            detalhes_historico = f"Itens aprovados movidos para a nova SC {nova_solicitacao.numero}."
            if observacoes:
                detalhes_historico += f" Observações: {observacoes}"

            # Adiciona histórico na solicitação original
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="Aprovação Parcial",
                detalhes=detalhes_historico
            )
            # Adiciona histórico na nova solicitação
            HistoricoSolicitacao.objects.create(
                solicitacao=nova_solicitacao,
                usuario=request.user,
                acao="Criação por Aprovação Parcial",
                detalhes=f"Originada da SC {solicitacao.numero}."
            )
            # --- FIM DO REGISTRO ---

            # Se a solicitação original ficou sem itens, marca como rejeitada/finalizada
            if not solicitacao.itens.exists():
                solicitacao.status = 'rejeitada' # Ou outro status que faça sentido
                solicitacao.aprovador = request.user
                solicitacao.data_aprovacao = timezone.now()
                solicitacao.observacoes_aprovacao = f"Todos os itens foram movidos para a SC {nova_solicitacao.numero}."
            
            solicitacao.save()
            
        return JsonResponse({
            'success': True, 
            'message': f'Aprovação parcial realizada! Nova SC {nova_solicitacao.numero} criada com {len(itens_aprovados_ids)} item(ns) aprovado(s).'
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Erro: {str(e)}'})

@login_required
def dashboard_relatorios(request):
    if request.user.perfil not in ['engenheiro', 'almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    # --- 1. Cálculos Gerais (Visão Geral) ---
    all_scs = SolicitacaoCompra.objects.all()
    aprovado_statuses = ['aprovada', 'aprovado_engenharia']
    cotacao_statuses = ['em_cotacao', 'aguardando_resposta', 'cotacao_selecionada']

    contexto_geral = {
        'total_solicitacoes': all_scs.count(),
        'solicitacoes_pendentes': all_scs.filter(status='pendente_aprovacao').count(),
        'solicitacoes_aprovadas': all_scs.filter(status__in=aprovado_statuses).count(),
        'solicitacoes_em_cotacao': all_scs.filter(status__in=cotacao_statuses).count(),
        'solicitacoes_finalizadas': all_scs.filter(status='finalizada').count(),
        'solicitacoes_recebidas': all_scs.filter(status='recebida').count(),
        'solicitacoes_rejeitadas': all_scs.filter(status='rejeitada').count(),
        'obras_ativas': Obra.objects.filter(ativa=True).count(),
    }

    # --- 2. Detalhes e Novas Métricas por Obra ---
    obras_com_scs = Obra.objects.filter(ativa=True, solicitacaocompra__isnull=False).distinct()
    obras_stats_detalhado = []

    for obra in obras_com_scs:
        obra_scs = SolicitacaoCompra.objects.filter(obra=obra)
        
        stats = {
            'obra': obra,
            'pendentes': obra_scs.filter(status='pendente_aprovacao').count(),
            'aprovadas': obra_scs.filter(status__in=aprovado_statuses).count(),
            'em_cotacao': obra_scs.filter(status__in=cotacao_statuses).count(),
            'finalizadas': obra_scs.filter(status='finalizada').count(),
            'a_caminho': obra_scs.filter(status='a_caminho').count(),
            'recebidas': obra_scs.filter(status__in=['recebida', 'recebida_parcial']).count(),
            'rejeitadas': obra_scs.filter(status='rejeitada').count(),
        }

        # MÉTRICA: Itens Mais Solicitados (Top 5 por Quantidade)
        stats['itens_mais_solicitados'] = ItemSolicitacao.objects.filter(
            solicitacao__obra=obra
        ).values('descricao', 'unidade').annotate(
            total_quantidade=Sum('quantidade')
        ).order_by('-total_quantidade')[:5]

        # MÉTRICA: Consumo por Categoria (Valor Total em R$)
        # ---- INÍCIO DA CORREÇÃO ----
        consumo_valor_categoria = ItemCotacao.objects.filter(
            cotacao__solicitacao__obra=obra, cotacao__vencedora=True
        ).annotate(
            subtotal=F('preco') * F('item_solicitacao__quantidade')
        ).values(
            categoria_nome=F('item_solicitacao__item_catalogo__categoria__categoria_mae__nome')
        ).annotate(
            valor_total=Sum('subtotal')
        ).order_by('-valor_total')
        
        # MÉTRICA: Consumo por Categoria (Quantidade Total de Itens)
        consumo_qtd_categoria = ItemSolicitacao.objects.filter(
            solicitacao__obra=obra, item_catalogo__isnull=False
        ).values(
            categoria_nome=F('item_catalogo__categoria__categoria_mae__nome')
        ).annotate(
            qtd_total=Sum('quantidade')
        ).order_by('-qtd_total')

        # Prepara os dados para os gráficos em formato JSON
        stats['consumo_valor_json'] = json.dumps({
            'labels': [c['categoria_nome'] or 'Sem Categoria Principal' for c in consumo_valor_categoria],
            'data': [float(c['valor_total']) for c in consumo_valor_categoria]
        })
        
        stats['consumo_qtd_json'] = json.dumps({
            'labels': [c['categoria_nome'] or 'Sem Categoria Principal' for c in consumo_qtd_categoria],
            'data': [float(c['qtd_total']) for c in consumo_qtd_categoria]
        })
        # ---- FIM DA CORREÇÃO ----

        obras_stats_detalhado.append(stats)

    context = {
        'geral': contexto_geral,
        'obras_stats_detalhado': obras_stats_detalhado,
    }
    
    return render(request, 'materiais/dashboard_relatorios.html', context)

@login_required
def buscar_solicitacoes(request):
    """Função de busca avançada para solicitações"""
    termo_busca = request.GET.get('q', '').strip()
    status_filtro = request.GET.get('status', '')
    obra_filtro = request.GET.get('obra', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    solicitante_filtro = request.GET.get('solicitante', '')
    
    if request.user.perfil == 'engenheiro':
        solicitacoes = SolicitacaoCompra.objects.all()
    else:
        solicitacoes = SolicitacaoCompra.objects.filter(solicitante=request.user)
    
    if termo_busca:
        solicitacoes = solicitacoes.filter(
            Q(numero__icontains=termo_busca) |
            Q(justificativa__icontains=termo_busca) |
            Q(itens__descricao__icontains=termo_busca)
        ).distinct()
    
    if status_filtro:
        solicitacoes = solicitacoes.filter(status=status_filtro)
    
    if obra_filtro:
        solicitacoes = solicitacoes.filter(obra_id=obra_filtro)
    
    if data_inicio:
        solicitacoes = solicitacoes.filter(data_criacao__gte=data_inicio)
    
    if data_fim:
        solicitacoes = solicitacoes.filter(data_criacao__lte=data_fim)
    
    if solicitante_filtro and request.user.perfil == 'engenheiro':
        solicitacoes = solicitacoes.filter(solicitante_id=solicitante_filtro)
    
    solicitacoes = solicitacoes.order_by('-data_criacao')
    
    obras = Obra.objects.filter(ativa=True).order_by('nome')
    usuarios = User.objects.filter(perfil__in=['almoxarife_obra', 'engenheiro']).order_by('first_name', 'username')
    
    context = {
        'solicitacoes': solicitacoes,
        'obras': obras,
        'usuarios': usuarios,
        'termo_busca': termo_busca,
        'status_filtro': status_filtro,
        'obra_filtro': obra_filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'solicitante_filtro': solicitante_filtro,
        'status_choices': SolicitacaoCompra.STATUS_CHOICES,
    }
    
    return render(request, 'materiais/buscar_solicitacoes.html', context)


@login_required
def exportar_relatorio(request):
    """Exporta relatório de solicitações em CSV"""
    if request.user.perfil not in ['engenheiro', 'almoxarife_escritorio']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
    
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="relatorio_solicitacoes_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    response.write('\ufeff')
    
    writer = csv.writer(response)
    
    writer.writerow([
        'Número SC', 'Status', 'Obra', 'Solicitante', 'Data Criação', 
        'Data Aprovação', 'Aprovador', 'Justificativa', 'Itens', 'Observações'
    ])
    
    solicitacoes = SolicitacaoCompra.objects.select_related(
        'obra', 'solicitante', 'aprovador'
    ).prefetch_related('itens').order_by('-data_criacao')
    
    for sc in solicitacoes:
        itens_str = '; '.join([
            f"{item.descricao} ({item.quantidade} {item.unidade})" 
            for item in sc.itens.all()
        ])
        
        writer.writerow([
            sc.numero,
            sc.get_status_display(),
            sc.obra.nome,
            sc.solicitante.get_full_name() or sc.solicitante.username,
            sc.data_criacao.strftime('%d/%m/%Y %H:%M') if sc.data_criacao else '',
            sc.data_aprovacao.strftime('%d/%m/%Y %H:%M') if sc.data_aprovacao else '',
            sc.aprovador.get_full_name() or sc.aprovador.username if sc.aprovador else '',
            sc.justificativa,
            itens_str,
            sc.observacoes_aprovacao or ''
        ])
    
    return response


@login_required
def duplicar_solicitacao(request, solicitacao_id):
    """Duplica uma solicitação existente"""
    if request.user.perfil not in ['almoxarife_obra', 'engenheiro']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
    
    solicitacao_original = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    
    if request.user.perfil != 'engenheiro' and solicitacao_original.solicitante != request.user:
        messages.error(request, 'Você só pode duplicar suas próprias solicitações.')
        return redirect('materiais:lista_solicitacoes')
    
    try:
        from django.db import transaction
    
        with transaction.atomic():
            nova_solicitacao = SolicitacaoCompra.objects.create(
                solicitante=request.user,
                obra=solicitacao_original.obra,
                data_necessidade=solicitacao_original.data_necessidade,
                justificativa=f"Duplicação da SC {solicitacao_original.numero} - {solicitacao_original.justificativa}",
                status='aprovada' if request.user.perfil == 'engenheiro' else 'pendente_aprovacao'
            )
            
            for item_original in solicitacao_original.itens.all():
                ItemSolicitacao.objects.create(
                    solicitacao=nova_solicitacao,
                    descricao=item_original.descricao,
                    quantidade=item_original.quantidade,
                    unidade=item_original.unidade,
                    observacoes=item_original.observacoes
                )
            
            if request.user.perfil == 'engenheiro':
                nova_solicitacao.aprovador = request.user
                nova_solicitacao.data_aprovacao = timezone.now()
                nova_solicitacao.save()
                messages.success(request, f'✅ SC {nova_solicitacao.numero} duplicada e aprovada automaticamente!')
            else:
                messages.success(request, f'✅ SC {nova_solicitacao.numero} duplicada com sucesso!')
            
        return redirect('materiais:lista_solicitacoes')
    
    except Exception as e:
        messages.error(request, f'Erro ao duplicar solicitação: {str(e)}')
        return redirect('materiais:lista_solicitacoes')




@login_required
def api_solicitacao_detalhes(request, solicitacao_id):
    try:
        # Adiciona 'destino' ao select_related para otimizar a busca
        solicitacao = SolicitacaoCompra.objects.select_related(
            'categoria_sc', 'solicitante', 'obra', 'destino'
        ).get(id=solicitacao_id)
        
        # Adiciona o campo 'destino' na resposta da API
        dados = {
            'numero': solicitacao.numero,
            'status': solicitacao.get_status_display(),
            'nome_descritivo': solicitacao.nome_descritivo,
            'solicitante': solicitacao.solicitante.get_full_name() or solicitacao.solicitante.username,
            'obra': solicitacao.obra.nome,
            'destino': solicitacao.destino.nome if solicitacao.destino else "Endereço da Obra", # NOVO
            'data_criacao': timezone.localtime(solicitacao.data_criacao).strftime('%d/%m/%Y'),
            'data_necessaria': solicitacao.data_necessidade.strftime('%d/%m/%Y'),
            'observacoes': solicitacao.justificativa,
            'is_emergencial': solicitacao.is_emergencial
        }

        itens = []
        for item in solicitacao.itens.all():
            itens.append({
                'descricao': item.descricao, 'quantidade': f"{item.quantidade:g}",
                'unidade': item.unidade, 'categoria': item.categoria or "Sem categoria"
            })
        dados['itens'] = itens

        historico = []
        for evento in solicitacao.historico.select_related('usuario').all():
            timestamp_local = timezone.localtime(evento.timestamp)
            historico.append({
                'status': evento.acao, 'timestamp': timestamp_local.strftime('%d/%m/%Y às %H:%M'),
                'usuario': evento.usuario.get_full_name() or evento.usuario.username if evento.usuario else "Sistema",
                'detalhes': evento.detalhes or ''
            })
        dados['historico'] = historico

        return JsonResponse(dados)
    
    except SolicitacaoCompra.DoesNotExist:
        return JsonResponse({'error': 'Solicitação não encontrada'}, status=404)
    
# Adicione esta nova função ao seu arquivo materiais/views.py cadastrar_itens
@login_required
def gerenciar_categorias(request):
    # PERMISSÃO CORRIGIDA PARA INCLUIR O DIRETOR
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        nome_categoria = request.POST.get('nome')

        if nome_categoria:
            if form_type == 'categoria_item':
                if not CategoriaItem.objects.filter(nome__iexact=nome_categoria).exists():
                    CategoriaItem.objects.create(nome=nome_categoria)
                    messages.success(request, f'Categoria de Item "{nome_categoria}" cadastrada!')
                else:
                    messages.error(request, 'Essa Categoria de Item já existe.')
            
            elif form_type == 'categoria_sc':
                if not CategoriaSC.objects.filter(nome__iexact=nome_categoria).exists():
                    CategoriaSC.objects.create(nome=nome_categoria)
                    messages.success(request, f'Categoria de SC "{nome_categoria}" cadastrada!')
                else:
                    messages.error(request, 'Essa Categoria de SC já existe.')
        else:
            messages.error(request, 'O nome da categoria não pode ser vazio.')
        return redirect('materiais:gerenciar_categorias')

    context = {
        'categorias_item': CategoriaItem.objects.all().order_by('nome'),
        'categorias_sc': CategoriaSC.objects.all().order_by('nome')
    }
    return render(request, 'materiais/gerenciar_categorias.html', context)

# Adicione esta nova função ao final de materiais/views.py

@login_required
def historico_aprovacoes(request):
    # Garante que apenas engenheiros acessem esta página
    if request.user.perfil != 'engenheiro':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    # Busca no banco de dados todas as SCs onde o 'aprovador' é o usuário logado
    solicitacoes_aprovadas = SolicitacaoCompra.objects.filter(
        aprovador=request.user
    ).select_related('obra', 'solicitante').order_by('-data_aprovacao')

    context = {
        'solicitacoes': solicitacoes_aprovadas
    }
    
    return render(request, 'materiais/historico_aprovacoes.html', context)

@login_required
def rejeitar_pelo_escritorio(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_escritorio':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='aprovada')
        
        # Opcional: pegar motivo da rejeição, se houver um campo no POST
        motivo = request.POST.get('motivo', 'Rejeitada pelo escritório antes da cotação.')

        solicitacao.status = 'rejeitada'
        solicitacao.aprovador = request.user # Registra quem tomou a decisão final
        solicitacao.data_aprovacao = timezone.now() # Registra quando
        solicitacao.observacoes_aprovacao = motivo
        solicitacao.save()
        
        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            acao="Solicitação Rejeitada",
            detalhes=motivo
        )

        messages.warning(request, f'A SC "{solicitacao.nome_descritivo}" foi rejeitada.')
        return redirect('materiais:gerenciar_cotacoes')

    # Redireciona de volta se o método não for POST
    return redirect('materiais:gerenciar_cotacoes')

# Adicione esta nova função ao seu arquivo views.py
@login_required
def escritorio_editar_sc(request, solicitacao_id):
    # View placeholder para a futura tela de edição
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    messages.info(request, f'A funcionalidade "Editar" para a SC {solicitacao.numero} está em desenvolvimento.')
    return redirect('materiais:gerenciar_cotacoes')


# Substitua sua função gerenciar_cotacoes por esta
@login_required
def gerenciar_cotacoes(request):
    # Verificação de permissão já inclui o 'diretor'
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    base_query = SolicitacaoCompra.objects.order_by('-is_emergencial', 'data_criacao')
    
    scs_para_iniciar = base_query.filter(status__in=['aprovada', 'aprovado_engenharia'])
    scs_em_cotacao = base_query.filter(status='em_cotacao')

    base_aguardando_resposta = base_query.filter(status='aguardando_resposta').prefetch_related('envios_cotacao__fornecedor', 'cotacoes')
    scs_pendentes_resposta = base_aguardando_resposta.filter(cotacoes__isnull=True)
    scs_parcialmente_recebidas = base_aguardando_resposta.filter(cotacoes__isnull=False).distinct()

    for sc in scs_parcialmente_recebidas:
        sc.cotacoes_recebidas_ids = set(sc.cotacoes.values_list('fornecedor_id', flat=True))

    scs_recebidas = base_query.filter(
        Q(status='cotacao_selecionada') |
        Q(status='aguardando_resposta', cotacoes__isnull=False)
    ).distinct().prefetch_related('cotacoes__fornecedor')

    aguardando_resposta_count = scs_pendentes_resposta.count()
    
    context = {
        'scs_para_iniciar': scs_para_iniciar,
        'scs_em_cotacao': scs_em_cotacao,
        'scs_recebidas': scs_recebidas,
        'aguardando_resposta_count': aguardando_resposta_count,
        'scs_pendentes_resposta': scs_pendentes_resposta,
        'scs_parcialmente_recebidas': scs_parcialmente_recebidas,
    }
    return render(request, 'materiais/gerenciar_cotacoes.html', context)

@login_required
def editar_solicitacao_escritorio(request, solicitacao_id):
    if request.user.perfil != 'almoxarife_escritorio':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:gerenciar_cotacoes')

    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status__in=['aprovada', 'aprovado_engenharia'])

    if request.method == 'POST':
        try:
            solicitacao.obra_id = request.POST.get('obra')
            # Captura e salva o 'destino'
            solicitacao.destino_id = request.POST.get('destino') if request.POST.get('destino') else None # NOVO
            solicitacao.data_necessidade = request.POST.get('data_necessidade')
            solicitacao.justificativa = request.POST.get('justificativa')
            solicitacao.is_emergencial = request.POST.get('is_emergencial') == 'on'
            solicitacao.categoria_sc_id = request.POST.get('categoria_sc')
            
            itens_json = request.POST.get('itens_json', '[]')
            itens_data = json.loads(itens_json)

            if not itens_data:
                messages.error(request, 'A solicitação deve ter pelo menos um item.')
                return redirect('materiais:editar_solicitacao_escritorio', solicitacao_id=solicitacao.id)

            with transaction.atomic():
                solicitacao.itens.all().delete()
                for item_data in itens_data:
                    item_catalogo = get_object_or_404(ItemCatalogo, id=item_data.get('item_id'))
                    ItemSolicitacao.objects.create(
                        solicitacao=solicitacao, item_catalogo=item_catalogo,
                        descricao=item_catalogo.descricao, unidade=item_catalogo.unidade.sigla,
                        categoria=str(item_catalogo.categoria), quantidade=float(item_data.get('quantidade')),
                        observacoes=item_data.get('observacao')
                    )
                solicitacao.save()
                HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="SC Editada", detalhes="A solicitação foi editada pelo escritório.")

            messages.success(request, f'Solicitação "{solicitacao.numero}" atualizada com sucesso!')
            return redirect(f"{reverse('materiais:gerenciar_cotacoes')}?tab=iniciar-cotacao")

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao salvar as alterações: {e}')
            return redirect('materiais:editar_solicitacao_escritorio', solicitacao_id=solicitacao.id)

    itens_existentes = []
    for item in solicitacao.itens.all():
        itens_existentes.append({
            "item_id": item.item_catalogo_id, "descricao": item.descricao, "unidade": item.unidade,
            "quantidade": f"{item.quantidade:g}", "observacao": item.observacoes
        })
    
    context = {
        'solicitacao': solicitacao,
        'itens_existentes_json': json.dumps(itens_existentes),
        'obras': Obra.objects.filter(ativa=True).order_by('nome'),
        'itens_catalogo_json': json.dumps(list(ItemCatalogo.objects.filter(ativo=True).values('id', 'codigo', 'descricao', 'unidade__sigla'))),
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'destinos_entrega': DestinoEntrega.objects.all().order_by('nome'), # NOVO
    }
    
    return render(request, 'materiais/editar_solicitacao.html', context)
@login_required
def api_buscar_fornecedores(request):
    termo = request.GET.get('term', '').strip()
    
    # --- CONSULTA CORRIGIDA ---
    # Agora, a busca é feita em ambos os campos: nome_fantasia E razao_social.
    # Usamos um objeto Q para criar uma condição OR na busca.
    fornecedores = Fornecedor.objects.filter(
        Q(nome_fantasia__icontains=termo) | Q(razao_social__icontains=termo),
        ativo=True
    ).order_by('nome_fantasia')[:10]
    
    # --- RESULTADO CORRIGIDO ---
    # O texto exibido no dropdown agora vem do campo 'nome_fantasia'.
    resultados = [{'id': f.id, 'text': f.nome_fantasia} for f in fornecedores]
    
    return JsonResponse(resultados, safe=False)

# materials/views.py

@login_required
def enviar_cotacao_fornecedor(request, solicitacao_id):
    if request.method == 'POST' and request.user.perfil in ['almoxarife_escritorio', 'diretor']:
        solicitacao_original = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
        
        fornecedores_ids = request.POST.getlist('fornecedor')
        itens_selecionados_ids = request.POST.getlist('itens_cotacao')
        prazo_resposta = request.POST.get('prazo_resposta')
        observacoes = request.POST.get('observacoes')
        # --- CAPTURANDO NOVOS CAMPOS ---
        forma_pagamento = request.POST.get('forma_pagamento')
        prazo_pagamento = request.POST.get('prazo_pagamento', 0)

        if not all([fornecedores_ids, itens_selecionados_ids]):
            messages.error(request, 'Selecione ao menos um fornecedor e um item.')
            return redirect('materiais:gerenciar_cotacoes')

        fornecedores_selecionados = Fornecedor.objects.filter(id__in=fornecedores_ids)
        itens_selecionados = ItemSolicitacao.objects.filter(id__in=itens_selecionados_ids, solicitacao=solicitacao_original)

        try:
            with transaction.atomic():
                # Esta lógica de dividir SCs filhas foi removida para simplificar.
                # A lógica agora sempre aplica os envios à SC original.
                
                solicitacao_original.status = 'aguardando_resposta'
                solicitacao_original.save()
                
                envios_criados_ids = []
                for fornecedor in fornecedores_selecionados:
                    envio = EnvioCotacao.objects.create(
                        solicitacao=solicitacao_original, fornecedor=fornecedor,
                        prazo_resposta=prazo_resposta if prazo_resposta else None,
                        observacoes=observacoes,
                        # --- SALVANDO NOVOS CAMPOS ---
                        forma_pagamento=forma_pagamento,
                        prazo_pagamento=prazo_pagamento
                    )
                    envio.itens.set(itens_selecionados)
                    envios_criados_ids.append(envio.id)
                
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao_original, usuario=request.user, acao="Cotação Enviada", 
                    detalhes=f"Cotação enviada para {len(fornecedores_selecionados)} fornecedor(es)."
                )
            
            # --- NOVO REDIRECIONAMENTO ---
            # Constrói a URL para a página de confirmação, passando os IDs dos envios criados
            envios_ids_query_param = ",".join(map(str, envios_criados_ids))
            redirect_url = f"{reverse('materiais:confirmar_envios_cotacao', args=[solicitacao_original.id])}?envios_ids={envios_ids_query_param}"
            return redirect(redirect_url)

        except Exception as e:
            messages.error(request, f"Erro ao enviar cotação: {e}")
            return redirect('materiais:gerenciar_cotacoes')
    
    messages.error(request, 'Acesso negado ou método inválido.')
    return redirect('materiais:gerenciar_cotacoes')

@login_required
def gerar_email_cotacao(request, envio_id):
    envio = get_object_or_404(EnvioCotacao.objects.select_related('solicitacao', 'fornecedor'), id=envio_id)
    
    itens_list_str = "\n".join([f"- {item.quantidade:g} {item.unidade} de {item.descricao}" for item in envio.itens.all()])
    
    email_body = (
        f"Prezados(as) da empresa {envio.fornecedor.nome_fantasia},\n\n"
        f"Gostaríamos de solicitar um orçamento para os seguintes itens, referentes à nossa Solicitação de Compra nº {envio.solicitacao.numero}:\n\n"
        f"{itens_list_str}\n\n"
        f"Condições sugeridas:\n"
        f"- Forma de Pagamento: {envio.get_forma_pagamento_display()}\n"
        f"- Prazo para Pagamento: {envio.prazo_pagamento} dias\n\n"
        f"Observações adicionais: {envio.observacoes}\n\n"
        f"Agradeceríamos se pudessem nos enviar a proposta até a data de {envio.prazo_resposta.strftime('%d/%m/%Y') if envio.prazo_resposta else 'o mais breve possível'}.\n\n"
        f"Atenciosamente,\n"
        f"{request.user.get_full_name() or request.user.username}"
    )
    
    url_retorno = reverse('materiais:confirmar_envios_cotacao', args=[envio.solicitacao.id]) + f"?envios_ids={envio.id}"

    context = {
        'envio': envio,
        'email_subject': f"Solicitação de Orçamento - SC {envio.solicitacao.numero}",
        'email_body': email_body,
        'url_retorno': url_retorno,
    }
    # A LINHA ABAIXO FOI CORRIGIDA COM O PARÊNTESE FINAL
    return render(request, 'materiais/gerar_email_cotacao.html', context)

@login_required
def enviar_automatico_placeholder(request):
    messages.info(request, 'A funcionalidade de envio automático de e-mail está em desenvolvimento.')
    return redirect('materiais:gerenciar_cotacoes')

@login_required
def confirmar_envio_manual(request, envio_id):
    envio = get_object_or_404(EnvioCotacao.objects.select_related('fornecedor', 'solicitacao'), id=envio_id)
    solicitacao = envio.solicitacao
    
    if solicitacao.status == 'em_cotacao':
        solicitacao.status = 'aguardando_resposta'
        solicitacao.save()
    
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="Confirmação de Envio Manual",
        # CORREÇÃO APLICADA AQUI: .nome -> .nome_fantasia
        detalhes=f"Usuário confirmou o envio do e-mail de cotação para o fornecedor {envio.fornecedor.nome_fantasia}."
    )
    
    # CORREÇÃO APLICADA AQUI: .nome -> .nome_fantasia
    messages.success(request, f"Envio de e-mail para {envio.fornecedor.nome_fantasia} confirmado com sucesso!")
    
    url_retorno = request.GET.get('next') or reverse('materiais:gerenciar_cotacoes') + '?tab=aguardando'
    return redirect(url_retorno)
    
@login_required
def api_dados_confirmacao_rm(request, cotacao_id):
    cotacao_vencedora = get_object_or_404(Cotacao.objects.select_related('fornecedor'), id=cotacao_id)
    solicitacao = cotacao_vencedora.solicitacao
    
    # Lógica para encontrar fornecedores pendentes
    fornecedores_com_cotacao = solicitacao.cotacoes.values_list('fornecedor_id', flat=True)
    envios_pendentes = solicitacao.envios_cotacao.select_related('fornecedor').exclude(fornecedor_id__in=fornecedores_com_cotacao)
    
    # Lógica para buscar os itens da cotação
    itens_da_cotacao = []
    for item_cotado in cotacao_vencedora.itens_cotados.select_related('item_solicitacao').all():
        item_solicitado = item_cotado.item_solicitacao
        itens_da_cotacao.append({
            'descricao': item_solicitado.descricao,
            'quantidade': f"{item_solicitado.quantidade:g}",
            'unidade': item_solicitado.unidade,
            'preco_total_item': f"R$ {(item_cotado.preco * item_solicitado.quantidade):.2f}".replace('.', ',')
        })

    dados = {
        'vencedora': {
            # CORRIGIDO AQUI
            'fornecedor': cotacao_vencedora.fornecedor.nome_fantasia,
            'valor': f"R$ {cotacao_vencedora.valor_total:.2f}".replace('.',','),
            'prazo': cotacao_vencedora.prazo_entrega or "Não informado",
            'pagamento': cotacao_vencedora.condicao_pagamento or "Não informado",
        },
        # E CORRIGIDO AQUI
        'pendentes': [envio.fornecedor.nome_fantasia for envio in envios_pendentes],
        'itens': itens_da_cotacao,
    }
    return JsonResponse(dados)

@login_required
def gerenciar_requisicoes(request):
    base_query = RequisicaoMaterial.objects.select_related(
        'cotacao_vencedora__fornecedor', 
        'assinatura_almoxarife', 
        'assinatura_diretor'
    ).order_by('-data_criacao')

    pendentes = base_query.filter(status_assinatura='pendente')
    aguardando_assinatura = base_query.filter(status_assinatura='aguardando_diretor')
    assinadas_enviadas = base_query.filter(status_assinatura='assinada')

    
    context = {
        'pendentes': pendentes,
        'aguardando_assinatura': aguardando_assinatura,
        'assinadas_enviadas': assinadas_enviadas,
    }
    return render(request, 'materiais/gerenciar_requisicoes.html', context)

@login_required
def assinar_requisicao(request, rm_id):
    if request.method == 'POST':
        rm = get_object_or_404(RequisicaoMaterial, id=rm_id)
        password = request.POST.get('password')

        if not request.user.check_password(password):
            messages.error(request, 'Senha incorreta. A assinatura não foi concluída.')
            return redirect('materiais:gerenciar_requisicoes')

        # --- INÍCIO DA LÓGICA ADICIONADA ---
        solicitacao = rm.solicitacao_origem # Pegamos a SC original
        # --- FIM DA LÓGICA ADICIONADA ---

        if request.user.perfil == 'almoxarife_escritorio' and not rm.assinatura_almoxarife:
            rm.assinatura_almoxarife = request.user
            rm.data_assinatura_almoxarife = timezone.now()
            rm.status_assinatura = 'aguardando_diretor'
            messages.success(request, f'RM {rm.numero} assinada por você. Aguardando Diretor.')
            
            # --- INÍCIO DA LÓGICA ADICIONADA ---
            # Adiciona um registro no histórico da SC
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao, usuario=request.user, acao="RM Assinada (1/2)",
                detalhes=f"Primeira assinatura (Almoxarife Escritório) confirmada para a RM {rm.numero}."
            )
            # --- FIM DA LÓGICA ADICIONADA ---
        
        elif request.user.perfil == 'diretor' and rm.assinatura_almoxarife and not rm.assinatura_diretor:
            rm.assinatura_diretor = request.user
            rm.data_assinatura_diretor = timezone.now()
            rm.status_assinatura = 'assinada'
            messages.success(request, f'RM {rm.numero} assinada! Todas as assinaturas foram coletadas.')

            # --- INÍCIO DA LÓGICA ADICIONADA ---
            # Adiciona um registro no histórico da SC
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao, usuario=request.user, acao="RM Assinada (2/2)",
                detalhes=f"Segunda assinatura (Diretor) confirmada. RM {rm.numero} pronta para envio."
            )
            # --- FIM DA LÓGICA ADICIONADA ---
        
        else:
            messages.warning(request, f'Não foi possível registrar a assinatura na RM {rm.numero}. Verifique o estado da requisição.')

        rm.save()
    return redirect('materiais:gerenciar_requisicoes')



@login_required
def enviar_rm_fornecedor(request, rm_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    rm = get_object_or_404(RequisicaoMaterial, id=rm_id)

    if rm.status_assinatura != 'assinada':
        messages.warning(request, f'A RM {rm.numero} não está no status "Assinada" e não pode ser enviada.')
        return redirect('materiais:gerenciar_requisicoes')

    if request.method == 'POST':
        # --- INÍCIO DA LÓGICA ADICIONADA E MODIFICADA ---
        # Usamos uma transação para garantir que todas as operações funcionem ou nenhuma
        with transaction.atomic():
            # 1. Pega a SC original
            solicitacao = rm.solicitacao_origem

            # 2. Atualiza a RM (como já fazia antes)
            rm.status_assinatura = 'enviada'
            rm.enviada_fornecedor = True
            rm.data_envio_fornecedor = timezone.now()
            rm.save()

            # 3. ATUALIZA O STATUS DA SC ORIGINAL PARA "A CAMINHO"
            solicitacao.status = 'a_caminho'
            solicitacao.save()

            # 4. ADICIONA O EVENTO CORRETO AO HISTÓRICO DA SC
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="Material a Caminho",
                detalhes=f"A RM {rm.numero} foi enviada para o fornecedor {rm.cotacao_vencedora.fornecedor.nome_fantasia}."
            )
        # --- FIM DA LÓGICA ADICIONADA E MODIFICADA ---
        
        messages.success(request, f'Envio da RM {rm.numero} confirmado com sucesso!')
        return redirect('materiais:gerenciar_requisicoes')

    context = {
        'rm': rm
    }
    return render(request, 'materiais/enviar_rm.html', context)

# NOVA VIEW DE API PARA OS DROPDOWNS EM CASCATA
def api_subcategorias(request, categoria_id):
    subcategorias = CategoriaItem.objects.filter(categoria_mae_id=categoria_id).order_by('nome')
    data = [{'id': sub.id, 'nome': sub.nome} for sub in subcategorias]
    return JsonResponse(data, safe=False)

@login_required
def editar_item(request, item_id):
    if request.user.perfil != 'almoxarife_escritorio':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    item_para_editar = get_object_or_404(ItemCatalogo, id=item_id)

    if request.method == 'POST':
        # Pega os dados enviados pelo formulário
        subcategoria_id = request.POST.get('subcategoria')
        descricao = request.POST.get('descricao')
        unidade_id = request.POST.get('unidade')
        tags_ids = request.POST.getlist('tags')
        status_ativo = request.POST.get('status') == 'on'

        if not all([descricao, subcategoria_id, unidade_id]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
        else:
            try:
                # Atualiza o objeto existente com os novos dados
                item_para_editar.categoria_id = subcategoria_id
                item_para_editar.descricao = descricao
                item_para_editar.unidade_id = unidade_id
                item_para_editar.ativo = status_ativo
                item_para_editar.tags.set(tags_ids)
                item_para_editar.save()

                messages.success(request, f'Item "{item_para_editar.descricao}" atualizado com sucesso!')
                return redirect('materiais:cadastrar_itens')
            except Exception as e:
                messages.error(request, f'Ocorreu um erro ao atualizar o item: {e}')

    # Lógica para carregar a página (método GET)
    context = {
        'item': item_para_editar,
        'categorias_principais': CategoriaItem.objects.filter(categoria_mae__isnull=True).order_by('nome'),
        # Passamos a subcategoria atual para o template saber qual selecionar
        'subcategorias_atuais': CategoriaItem.objects.filter(categoria_mae=item_para_editar.categoria.categoria_mae).order_by('nome'),
        'unidades': UnidadeMedida.objects.all().order_by('nome'),
        'tags': Tag.objects.all().order_by('nome'),
    }
    return render(request, 'materiais/editar_item.html', context)

login_required
def visualizar_rm_pdf(request, rm_id):
    rm = get_object_or_404(
        RequisicaoMaterial.objects.select_related(
            'solicitacao_origem__solicitante',
            'solicitacao_origem__obra',
            'solicitacao_origem__destino',
            'cotacao_vencedora__fornecedor'
        ), 
        id=rm_id
    )

    # ===================================================================
    # INÍCIO DA LINHA ADICIONADA: Calcula o subtotal apenas dos itens
    # ===================================================================
    subtotal_itens = rm.valor_total - rm.cotacao_vencedora.valor_frete
    # ===================================================================
    # FIM DA LINHA ADICIONADA
    # ===================================================================

    context = {
        'rm': rm,
        'solicitacao': rm.solicitacao_origem,
        'fornecedor': rm.cotacao_vencedora.fornecedor,
        'itens_cotados': rm.cotacao_vencedora.itens_cotados.select_related('item_solicitacao').all(),
        'empresa': rm_config.DADOS_EMPRESA,
        'subtotal_itens': subtotal_itens, # <-- Adiciona o valor ao contexto
    }
    
    html_string = render_to_string('materiais/rm_pdf_template.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
    
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="RM_{rm.numero}.pdf"'
    return response

@login_required
def api_itens_filtrados(request):
    categoria_id = request.GET.get('categoria_id')
    subcategoria_id = request.GET.get('subcategoria_id')
    
    itens_query = ItemCatalogo.objects.filter(ativo=True)
    
    # Prioriza o filtro de subcategoria, se ele for especificado
    if subcategoria_id:
        itens_query = itens_query.filter(categoria_id=subcategoria_id)
    # Se não houver subcategoria, filtra pela categoria principal
    elif categoria_id:
        # Busca itens cuja categoria tenha a categoria principal informada como 'mãe'
        itens_query = itens_query.filter(categoria__categoria_mae_id=categoria_id)
    
    # Se nenhum filtro for aplicado, retorna todos os itens (comportamento inicial)
    
    itens = list(itens_query.select_related('unidade').values('id', 'codigo', 'descricao', 'unidade__sigla'))
    return JsonResponse(itens, safe=False)

@login_required
def confirmar_envios_cotacao(request, solicitacao_id):
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
    # Pega os IDs dos envios da query string da URL
    envios_ids_str = request.GET.get('envios_ids', '')
    if envios_ids_str:
        envios_ids = [int(eid) for eid in envios_ids_str.split(',')]
        envios = EnvioCotacao.objects.filter(id__in=envios_ids).select_related('fornecedor').prefetch_related('itens')
    else:
        envios = EnvioCotacao.objects.none()

    context = {
        'solicitacao': solicitacao,
        'envios': envios
    }
    return render(request, 'materiais/confirmar_envios.html', context)

@login_required
def api_get_itens_para_receber(request, solicitacao_id):
    try:
        sc = SolicitacaoCompra.objects.select_related('solicitante', 'obra').get(id=solicitacao_id)
        
        itens_data = []
        for item in sc.itens.all():
            total_recebido = ItemRecebido.objects.filter(item_solicitado=item).aggregate(total=Sum('quantidade_recebida'))['total'] or 0
            quantidade_pendente = item.quantidade - total_recebido
            
            if quantidade_pendente > 0:
                itens_data.append({
                    'id': item.id,
                    'descricao': item.descricao,
                    'quantidade_solicitada': f"{item.quantidade:g}",
                    'quantidade_pendente': f"{quantidade_pendente:g}",
                    'unidade': item.unidade,
                })
        
        return JsonResponse({
            'success': True,
            'sc': {
                'numero': sc.numero,
                'solicitante': sc.solicitante.get_full_name() or sc.solicitante.username,
                'obra': sc.obra.nome,
                'data_criacao': sc.data_criacao.strftime('%d/%m/%Y')
            },
            'itens': itens_data,
        })
    except SolicitacaoCompra.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Solicitação não encontrada'}, status=404)


@login_required
def registrar_recebimento(request):
    if request.user.perfil != 'almoxarife_obra':
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                solicitacao_id = request.POST.get('solicitacao_id')
                sc = get_object_or_404(SolicitacaoCompra, id=solicitacao_id)
                
                # 1. Cria o registro do evento de recebimento
                novo_recebimento = Recebimento.objects.create(
                    solicitacao=sc,
                    recebedor=request.user,
                    observacoes=request.POST.get('observacoes', ''),
                    nota_fiscal=request.FILES.get('nota_fiscal'),
                    sc_assinada=request.FILES.get('sc_assinada'),
                    boleto_comprovante=request.FILES.get('boleto_comprovante')
                )

                # 2. Cria os registros para cada item recebido no formulário atual
                itens_selecionados_ids = request.POST.getlist('itens_selecionados')
                for item_id in itens_selecionados_ids:
                    quantidade_str = request.POST.get(f'quantidade_recebida_{item_id}')
                    if quantidade_str and float(quantidade_str) > 0:
                        ItemRecebido.objects.create(
                            recebimento=novo_recebimento,
                            item_solicitado_id=item_id,
                            quantidade_recebida=float(quantidade_str),
                            observacoes=request.POST.get(f'observacoes_{item_id}', '')
                        )

                # 3. VERIFICA O STATUS GERAL DA SC (LÓGICA CORRIGIDA)
                total_itens_sc = sc.itens.count()
                itens_completos = 0
                for item_solicitado in sc.itens.all():
                    # Soma tudo que já foi recebido para este item em todos os recebimentos
                    total_recebido_do_item = item_solicitado.recebimentos.aggregate(
                        total=Sum('quantidade_recebida')
                    )['total'] or 0
                    
                    if total_recebido_do_item >= item_solicitado.quantidade:
                        itens_completos += 1
                
                # Decide o novo status da SC
                if itens_completos == total_itens_sc:
                    sc.status = 'recebida'
                    acao_historico = "Material Recebido (Total)"
                else:
                    sc.status = 'recebida_parcial'
                    acao_historico = "Material Recebido (Parcial)"
                
                sc.save()

                # 4. Cria registro no histórico
                HistoricoSolicitacao.objects.create(
                    solicitacao=sc, usuario=request.user, acao=acao_historico,
                    detalhes=f"Recebimento de {len(itens_selecionados_ids)} item(ns) registrado por {request.user.get_full_name()}."
                )
                
                messages.success(request, f'Recebimento da SC {sc.numero} registrado com sucesso!')
                return redirect('materiais:dashboard')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao registrar o recebimento: {e}')
    
    # Lógica para GET (carregar a página)
    user_obras = request.user.obras.all()
    scs_a_receber = SolicitacaoCompra.objects.filter(
        obra__in=user_obras,
        status__in=['a_caminho', 'recebida_parcial'] # Agora também busca as parciais
    ).order_by('data_criacao')
    
    context = {
        'scs_a_receber': scs_a_receber
    }
    return render(request, 'materiais/registrar_recebimento.html', context)

@login_required
def editar_solicitacao_analise(request, solicitacao_id):
    # Garante que apenas engenheiros e diretores possam usar esta função.
    if request.user.perfil not in ['engenheiro', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')

    # Busca a solicitação que está pendente de aprovação
    solicitacao = get_object_or_404(SolicitacaoCompra, id=solicitacao_id, status='pendente_aprovacao')

    if request.method == 'POST':
        try:
            # A lógica para salvar os dados é a mesma da tela do escritório
            solicitacao.obra_id = request.POST.get('obra')
            solicitacao.destino_id = request.POST.get('destino') if request.POST.get('destino') else None
            solicitacao.data_necessidade = request.POST.get('data_necessidade')
            solicitacao.justificativa = request.POST.get('justificativa')
            solicitacao.is_emergencial = request.POST.get('is_emergencial') == 'on'
            solicitacao.categoria_sc_id = request.POST.get('categoria_sc')
            
            itens_json = request.POST.get('itens_json', '[]')
            itens_data = json.loads(itens_json)

            if not itens_data:
                messages.error(request, 'A solicitação deve ter pelo menos um item.')
                return redirect('materiais:analisar_editar_solicitacao', solicitacao_id=solicitacao.id)

            with transaction.atomic():
                # Remove os itens antigos para substituí-los pelos novos
                solicitacao.itens.all().delete()
                for item_data in itens_data:
                    item_catalogo = get_object_or_404(ItemCatalogo, id=item_data.get('item_id'))
                    ItemSolicitacao.objects.create(
                        solicitacao=solicitacao,
                        item_catalogo=item_catalogo,
                        descricao=item_catalogo.descricao,
                        unidade=item_catalogo.unidade.sigla,
                        categoria=str(item_catalogo.categoria),
                        quantidade=float(item_data.get('quantidade')),
                        observacoes=item_data.get('observacao')
                    )
                
                # *** PONTO CHAVE DA MUDANÇA ***
                # Ao salvar, o status muda para o próximo passo do fluxo do engenheiro.
                solicitacao.status = 'aprovado_engenharia'
                solicitacao.aprovador = request.user
                solicitacao.data_aprovacao = timezone.now()
                solicitacao.save()
                
                HistoricoSolicitacao.objects.create(
                    solicitacao=solicitacao,
                    usuario=request.user,
                    acao="Aprovada com Edição",
                    detalhes="A solicitação foi editada e aprovada pelo engenheiro."
                )

            messages.success(request, f'Solicitação "{solicitacao.numero}" foi editada e aprovada com sucesso!')
            # Redireciona de volta para a lista de análise
            return redirect('materiais:analisar_solicitacoes')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao salvar as alterações: {e}')
            return redirect('materiais:analisar_editar_solicitacao', solicitacao_id=solicitacao.id)

    # A lógica para carregar a página (GET) é a mesma da tela do escritório
    itens_existentes = []
    for item in solicitacao.itens.all():
        itens_existentes.append({
            "item_id": item.item_catalogo_id, "descricao": item.descricao, "unidade": item.unidade,
            "quantidade": f"{item.quantidade:g}", "observacao": item.observacoes
        })
    
    context = {
        'solicitacao': solicitacao,
        'itens_existentes_json': json.dumps(itens_existentes),
        'obras': Obra.objects.filter(ativa=True).order_by('nome'),
        'itens_catalogo_json': json.dumps(list(ItemCatalogo.objects.filter(ativo=True).values('id', 'codigo', 'descricao', 'unidade__sigla'))),
        'categorias_sc': CategoriaSC.objects.all().order_by('nome'),
        'destinos_entrega': DestinoEntrega.objects.all().order_by('nome'),
    }
    
    # *** PONTO CHAVE DA REUTILIZAÇÃO ***
    # Nós renderizamos o mesmo template que o escritório usa!
    return render(request, 'materiais/editar_solicitacao.html', context)

@login_required
def editar_fornecedor(request, fornecedor_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        messages.error(request, 'Acesso negado.')
        return redirect('materiais:dashboard')
    
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    # A lógica de POST/edição ficaria aqui, mas por enquanto retorna um placeholder simples.
    
    messages.info(request, f'Funcionalidade de edição para {fornecedor.nome_fantasia} em desenvolvimento.')
    return redirect('materiais:gerenciar_fornecedores')


# Nova View para Alteração de Status (ativar/inativar via AJAX)
@login_required
@csrf_exempt # Permite o POST simples via AJAX/fetch
def alterar_status_fornecedor(request, fornecedor_id):
    if request.user.perfil not in ['almoxarife_escritorio', 'diretor']:
        return JsonResponse({'success': False, 'message': 'Acesso negado.'}, status=403)
        
    if request.method == 'POST':
        fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
        novo_status_str = request.POST.get('ativo', 'false')
        
        # Converte a string 'true'/'false' em booleano
        novo_status = novo_status_str == 'true'

        try:
            fornecedor.ativo = novo_status
            fornecedor.save()
            
            acao = "Ativado" if novo_status else "Inativado"
            messages.success(request, f'Fornecedor {fornecedor.nome_fantasia} {acao} com sucesso!')
            return JsonResponse({'success': True})
        
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Método não permitido.'})
