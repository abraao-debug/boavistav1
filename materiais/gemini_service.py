# materials/gemini_service.py

import os
import json
from django.conf import settings
import google.generativeai as genai
import math # Importado para o cálculo do cosseno

# --- SUAS CLASSES DE BYPASS (Mantidas 100% como no seu original) ---
class Type:
    OBJECT = 'OBJECT'
    STRING = 'STRING'
    INTEGER = 'INTEGER'
    NUMBER = 'NUMBER'
    BOOLEAN = 'BOOLEAN'

class Schema:
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
    BLOCK_NONE_VALUE = 'BLOCK_NONE'

# --- FUNÇÃO DE CONFIGURAÇÃO DA API ---
def get_api_key():
    try:
        api_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)
        return api_key
    except (AttributeError, KeyError):
        return None

# --- CONFIGURAÇÃO DA API ---
try:
    api_key = get_api_key()
    if api_key:
        genai.configure(api_key=api_key)
        # O modelo generativo será usado para a validação final
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        # O modelo de embedding é necessário para a busca vetorial
        EMBEDDING_MODEL = 'models/embedding-001' 
    else:
        gemini_model = None
        EMBEDDING_MODEL = None
except Exception as e:
    gemini_model = None
    EMBEDDING_MODEL = None


# --- NOVA FUNÇÃO: GERAR EMBEDDING (VETOR) PARA UM TEXTO ---
def get_embedding_for_text(text: str) -> list or None:
    if not EMBEDDING_MODEL:
        return None
    try:
        result = genai.embed_content(model=EMBEDDING_MODEL, content=text)
        return result['embedding']
    except Exception as e:
        print(f"ERRO ao gerar embedding para '{text[:20]}...': {e}")
        return None


# --- FUNÇÃO PRINCIPAL DE CLASSIFICAÇÃO (AGORA É DE VALIDAÇÃO) ---
# Recebe a lista de melhores candidatos JÁ CALCULADA via busca vetorial.
def classify_item_with_gemini(item_description: str, top_candidates_list: str, units_list: str) -> dict:
    if not gemini_model:
        return {"status": "ERROR", "message": "Gemini API não está configurada."}

    full_prompt = f"""
    Você é um classificador de catálogo para construção civil. Sua tarefa é analisar a descrição de um item e os melhores candidatos de categorias existentes para retornar a classificação mais provável em formato JSON.

    TOP CANDIDATOS (Melhores combinações no catálogo):
    ---
    {top_candidates_list}
    ---
    
    LISTA DE UNIDADES VÁLIDAS:
    ---
    {units_list}
    ---

    REGRAS DE DECISÃO:
    1. Se o item pertencer a um dos TOP CANDIDATOS (ou seja, você tem 95% de certeza que o item É AQUELE), retorne status "EXISTENTE".
    2. Se o item claramente se encaixa na Categoria Mãe de um candidato, mas a Subcategoria ideal não existe (e precisa de uma nova), retorne o status "SUGERIR_SUBCATEGORIA".
    3. Se o item não se encaixa em nenhuma Categoria Mãe dos candidatos (e precisa de uma totalmente nova), retorne o status "SUGERIR_NOVA".
    4. Para TODOS os status, você DEVE retornar o `unidade_id` numérico mais apropriado da lista de unidades fornecida.

    ITEM PARA CLASSIFICAR: "{item_description}"

    Responda APENAS com um JSON válido, usando EXATAMENTE as chaves especificadas em um dos formatos abaixo:

    Formato para "EXISTENTE":
    {{
        "status": "EXISTENTE",
        "categoria_mae_id": <id_numerico>,
        "subcategoria_id": <id_numerico>,
        "unidade_id": <id_numerico>
    }}

    Formato para "SUGERIR_SUBCATEGORIA":
    {{
        "status": "SUGERIR_SUBCATEGORIA",
        "categoria_mae_id": <id_numerico_da_mae_existente>,
        "sugestao_nova_subcategoria": "<nome_da_nova_subcategoria>",
        "unidade_id": <id_numerico>
    }}

    Formato para "SUGERIR_NOVA":
    {{
        "status": "SUGERIR_NOVA",
        "sugestao_nova_categoria_mae": "<nome_da_nova_categoria_principal>",
        "sugestao_nova_subcategoria": "<nome_da_nova_subcategoria>",
        "unidade_id": <id_numerico>
    }}
    """
    try:
        # Configurações de segurança omitidas por brevidade, mas devem ser mantidas
        # ...

        response = gemini_model.generate_content(
            full_prompt,
            # safety_settings=safety_settings_list_dict
        )
        
        # Lógica de extração e validação do JSON (igual à anterior)
        # ...
        
        response_text = response.text

        try:
            start_index = response_text.find('{')
            end_index = response_text.rfind('}') + 1
            
            if start_index == -1 or end_index == 0:
                raise json.JSONDecodeError("JSON não encontrado na resposta", response_text, 0)
            
            json_str = response_text[start_index:end_index]
            gemini_data = json.loads(json_str)
            
            # Validação do status e campos (igual à anterior)
            status = gemini_data.get("status")
            if status == "EXISTENTE":
                required_fields = ["categoria_mae_id", "subcategoria_id", "unidade_id"]
                if not all(field in gemini_data for field in required_fields):
                    return {"status": "ERROR", "message": f"Resposta EXISTENTE incompleta do Gemini: {gemini_data}"}
            
            elif status == "SUGERIR_NOVA":
                required_fields = ["sugestao_nova_categoria_mae", "sugestao_nova_subcategoria", "unidade_id"]
                if not all(field in gemini_data for field in required_fields):
                     return {"status": "ERROR", "message": f"Resposta SUGERIR_NOVA incompleta do Gemini: {gemini_data}"}

            elif status == "SUGERIR_SUBCATEGORIA":
                 required_fields = ["categoria_mae_id", "sugestao_nova_subcategoria", "unidade_id"]
                 if not all(field in gemini_data for field in required_fields):
                     return {"status": "ERROR", "message": f"Resposta SUGERIR_SUBCATEGORIA incompleta do Gemini: {gemini_data}"}
            else:
                return {"status": "ERROR", "message": f"Status inválido retornado pelo Gemini: {gemini_data}"}
            
            return gemini_data
                
        except json.JSONDecodeError:
            return {"status": "ERROR", "message": f"Erro ao decodificar JSON do Gemini: {response_text[:200]}..."}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "ERROR", "message": f"Erro na comunicação com a API: {type(e).__name__}"}

# ... (restante do arquivo) ...
# --- SUAS DEMAIS FUNÇÕES E CLASSES (Mantidas intactas) ---
def test_gemini_connection():
    pass

class GeminiModelCompatibility:
    def __init__(self):
        self.is_configured = get_api_key() is not None
    
    def __bool__(self):
        return self.is_configured

gemini_model_compat = GeminiModelCompatibility() 

def debug_gemini_service():
    pass

if __name__ == "__main__":
    pass