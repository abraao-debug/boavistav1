# materials/gemini_service.py (VERSÃO CORRIGIDA COMPLETA)

import os
import json
from django.conf import settings
import google.generativeai as genai

# --- 1. CONFIGURAÇÃO DO MODELO E CHAVE ---
try:
    # Múltiplas tentativas para encontrar a API key
    API_KEY = None

    # Tentativa 1: Django settings
    if hasattr(settings, 'GEMINI_API_KEY'):
        API_KEY = settings.GEMINI_API_KEY

    # Tentativa 2: Variável de ambiente
    if not API_KEY:
        API_KEY = os.environ.get('GEMINI_API_KEY')

    if not API_KEY:
        raise ValueError("GEMINI_API_KEY não encontrada. Configure no settings.py ou como variável de ambiente.")

    genai.configure(api_key=API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    print(f"✅ Gemini configurado com sucesso!")

except Exception as e:
    print(f"❌ ATENÇÃO: Falha na configuração do Gemini API. {e}")
    gemini_model = None

# --- 2. FUNÇÃO PRINCIPAL DE CLASSIFICAÇÃO (VERSÃO CORRIGIDA) ---
def classify_item_with_gemini(item_description: str, categories_and_units_list: str) -> dict:
    """
    Chama a API do Gemini para classificar um item em categorias existentes ou sugerir novas.
    Agora inclui também sugestão de unidade de medida.
    """
    if not gemini_model:
        return {"status": "ERROR", "message": "Gemini API não está configurada."}

    prompt = f"""
Você é um classificador de catálogo para construção civil. Sua tarefa é mapear uma descrição de item para uma das categorias/subcategorias E unidades de medida fornecidas.

{categories_and_units_list}

REGRAS:
1. Se o item se encaixar perfeitamente em uma subcategoria existente (95% de certeza), retorne status "EXISTENTE" com os IDs numéricos da categoria E da unidade.
2. Se o item não se encaixar em nenhuma subcategoria existente, retorne status "SUGERIR_NOVA" com nomes para nova categoria mãe, subcategoria E unidade de medida.
3. A nova categoria mãe DEVE ser uma das listadas, a menos que seja um conceito totalmente novo.
4. SEMPRE sugira uma unidade de medida apropriada para o item.

ITEM PARA CLASSIFICAR: {item_description}

Responda APENAS em formato JSON válido com uma das estruturas:

Para item existente:
{{
    "status": "EXISTENTE",
    "categoria_mae_id": 1,
    "subcategoria_id": 5,
    "unidade_id": 3
}}

Para nova categoria:
{{
    "status": "SUGERIR_NOVA",
    "nova_categoria_mae": "Nome da Categoria Mãe",
    "nova_subcategoria": "Nome da Nova Subcategoria",
    "nova_unidade": "Nome da Nova Unidade",
    "nova_unidade_sigla": "Sigla"
}}
"""

    try:
        # Configurações de segurança mais permissivas
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]

        response = gemini_model.generate_content(
            prompt,
            safety_settings=safety_settings
        )

        # Verificar se a resposta foi bloqueada ou está vazia
        if not hasattr(response, 'text') or not response.text:
            # Tentar acessar de forma alternativa
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        response_text = candidate.content.parts[0].text
                    else:
                        return {"status": "ERROR", "message": "Resposta bloqueada pelo sistema de segurança do Gemini."}
                else:
                    return {"status": "ERROR", "message": "Resposta bloqueada pelo sistema de segurança do Gemini."}
            else:
                return {"status": "ERROR", "message": "Nenhuma resposta recebida do Gemini."}
        else:
            response_text = response.text

        # Limpar a resposta (remover markdown se houver)
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '')
        elif response_text.startswith('```'):
            response_text = response_text.replace('```', '')

        # Tentar fazer o parse do JSON
        try:
            gemini_data = json.loads(response_text)
            
            # Validar se tem os campos obrigatórios
            if gemini_data.get("status") == "EXISTENTE":
                required_fields = ["categoria_mae_id", "subcategoria_id", "unidade_id"]
                if all(field in gemini_data for field in required_fields):
                    return gemini_data
                else:
                    return {"status": "ERROR", "message": f"Resposta incompleta do Gemini: {gemini_data}"}
                    
            elif gemini_data.get("status") == "SUGERIR_NOVA":
                required_fields = ["nova_categoria_mae", "nova_subcategoria", "nova_unidade", "nova_unidade_sigla"]
                if all(field in gemini_data for field in required_fields):
                    return gemini_data
                else:
                    return {"status": "ERROR", "message": f"Resposta incompleta do Gemini: {gemini_data}"}
            else:
                return {"status": "ERROR", "message": f"Status inválido retornado pelo Gemini: {gemini_data}"}
                
        except json.JSONDecodeError as e:
            return {"status": "ERROR", "message": f"Erro ao decodificar JSON do Gemini: {response_text[:200]}..."}

    except Exception as e:
        return {"status": "ERROR", "message": f"Erro na comunicação com a API: {str(e)}"}