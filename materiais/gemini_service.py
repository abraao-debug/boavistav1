# materials/gemini_service.py (CÓDIGO CORRIGIDO FINAL)

import os
import json
from django.conf import settings
import google.generativeai as genai

# --- CLASSES DE BYPASS PARA CONTORNAR O ERRO ESTRUTURAL ---
# Definimos as classes que o Gemini está falhando em expor
class Type:
    OBJECT = 'OBJECT'
    STRING = 'STRING'
    INTEGER = 'INTEGER'
    NUMBER = 'NUMBER'
    BOOLEAN = 'BOOLEAN'

class Schema:
    """Imita genai.types.Schema para contornar o Attribute Error."""
    def __init__(self, type, description=None, properties=None, items=None, required=None):
        self.type = type
        self.description = description
        self.properties = properties
        self.items = items
        self.required = required

class SafetySetting:
    def __init__(self, category, threshold):
        self.category = category
        self.threshold = threshold

class HarmCategory:
    HARM_CATEGORY_HARASSMENT = 'HARM_CATEGORY_HARASSMENT'
    HARM_CATEGORY_HATE_SPEECH = 'HARM_CATEGORY_HATE_SPEECH'
    HARM_CATEGORY_SEXUALLY_EXPLICIT = 'HARM_CATEGORY_SEXUALLY_EXPLICIT'
    HARM_CATEGORY_DANGEROUS_CONTENT = 'HARM_CATEGORY_DANGEROUS_CONTENT'

class HarmBlockThreshold:
    # 0 = BLOCK_NONE
    BLOCK_NONE_VALUE = 0 


# --- 1. CONFIGURAÇÃO DO MODELO E CHAVE ---
try:
    API_KEY = None
    if hasattr(settings, 'GEMINI_API_KEY'):
        API_KEY = settings.GEMINI_API_KEY
    if not API_KEY:
        API_KEY = os.environ.get('GEMINI_API_KEY')
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY não encontrada.")

    genai.configure(api_key=API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    print(f"✅ Gemini configurado com sucesso!")

except Exception as e:
    print(f"❌ ATENÇÃO: Falha na configuração do Gemini API. {e}")
    gemini_model = None


# --- 2. DEFINIÇÃO DO SCHEMA DE SAÍDA (Usando Classes Locais) ---

CLASSIFICATION_SCHEMA = Schema(
    type=Type.OBJECT,
    properties={
        "status": Schema(type=Type.STRING, description="Status da classificação."),
        "categoria_mae_id": Schema(type=Type.INTEGER, description="ID da Categoria Mãe."),
        "subcategoria_id": Schema(type=Type.INTEGER, description="ID da Subcategoria sugerida."),
        "unidade_id": Schema(type=Type.INTEGER, description="ID da Unidade de Medida."),
        "nova_categoria_mae": Schema(type=Type.STRING, description="Nome da nova Categoria Mãe."),
        "nova_subcategoria": Schema(type=Type.STRING, description="Nome da nova Subcategoria."),
        "nova_unidade": Schema(type=Type.STRING, description="Nome completo da nova unidade."),
        "nova_unidade_sigla": Schema(type=Type.STRING, description="Sigla da nova unidade."),
    },
    required=["status"]
)

# --- 3. FUNÇÃO PRINCIPAL DE CLASSIFICAÇÃO ---

def classify_item_with_gemini(item_description: str, categories_and_units_list: str) -> dict:
    """
    Chama a API do Gemini para classificar um item em categorias existentes ou sugerir novas.
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
"""
    try:
        # Configuração de segurança
        # CORREÇÃO CRÍTICA: Usando lista de Dicionários SIMPLES (string, número) 
        # para a segurança, contornando o erro de objeto desconhecido.
        safety_settings_list_dict = [
            {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': HarmBlockThreshold.BLOCK_NONE_VALUE},
            {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': HarmBlockThreshold.BLOCK_NONE_VALUE},
            {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': HarmBlockThreshold.BLOCK_NONE_VALUE},
            {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': HarmBlockThreshold.BLOCK_NONE_VALUE}
        ]

        # Chamada final: Passando segurança e schema DIRETAMENTE
        response = gemini_model.generate_content(
            prompt,
            safety_settings=safety_settings_list_dict
        )
        
        # O restante da lógica de validação robusta é mantida aqui.

        if not hasattr(response, 'text') or not response.text:
             if hasattr(response, 'candidates') and response.candidates:
                 candidate = response.candidates[0]
                 if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts') and candidate.content.parts:
                     response_text = candidate.content.parts[0].text
                 else:
                     return {"status": "ERROR", "message": "Resposta incompleta ou bloqueada pelo Gemini."}
             else:
                 return {"status": "ERROR", "message": "Nenhuma resposta recebida do Gemini."}
        else:
             response_text = response.text

        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '')
        elif response_text.startswith('```'):
            response_text = response_text.replace('```', '')

        try:
             gemini_data = json.loads(response_text)
             
             if gemini_data.get("status") == "EXISTENTE":
                 required_fields = ["categoria_mae_id", "subcategoria_id", "unidade_id"]
                 if all(field in gemini_data for field in required_fields):
                     return gemini_data
                 else:
                     return {"status": "ERROR", "message": f"Resposta EXISTENTE incompleta do Gemini: {gemini_data}"}
             
             elif gemini_data.get("status") == "SUGERIR_NOVA":
                 required_fields = ["nova_categoria_mae", "nova_subcategoria", "nova_unidade", "nova_unidade_sigla"]
                 if all(field in gemini_data for field in required_fields):
                     return gemini_data
                 else:
                     return {"status": "ERROR", "message": f"Resposta SUGERIR_NOVA incompleta do Gemini: {gemini_data}"}
             
             else:
                 return {"status": "ERROR", "message": f"Status inválido retornado pelo Gemini: {gemini_data}"}
                 
        except json.JSONDecodeError as e:
            return {"status": "ERROR", "message": f"Erro ao decodificar JSON do Gemini: {response_text[:200]}..."}

    except Exception as e:
        return {"status": "ERROR", "message": f"Erro na comunicação com a API: {str(e)}"}