# materials/gemini_service.py (VERSÃO CORRIGIDA E ATUALIZADA)

import os
import json
import requests
from django.conf import settings

# --- 1. CONFIGURAÇÃO DA API ---
def get_api_key():
    """Obtém a chave API do Gemini das configurações do Django"""
    try:
        return settings.GEMINI_API_KEY
    except AttributeError:
        print("ERRO: GEMINI_API_KEY não encontrada nas configurações do Django")
        return None

# --- 2. FUNÇÃO PARA TESTAR A CONEXÃO ---
def test_gemini_connection():
    """Testa se a API do Gemini está funcionando"""
    api_key = get_api_key()
    if not api_key:
        return False, "Chave API não configurada"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Teste de conexão"
                    }
                ]
            }
        ]
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            return True, "Conexão OK"
        else:
            return False, f"Erro HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"Erro de conexão: {str(e)}"

# --- 3. FUNÇÃO PRINCIPAL DE CLASSIFICAÇÃO ---
def classify_item_with_gemini(item_description: str, categories_list: str) -> dict:
    """
    Chama a API do Gemini para classificar um item em categorias existentes ou sugerir novas.
    
    Args:
        item_description (str): Descrição do item a ser classificado
        categories_list (str): Lista das categorias e subcategorias existentes
    
    Returns:
        dict: Resultado da classificação com status e dados
    """
    
    # Verificar se a API está configurada
    api_key = get_api_key()
    if not api_key:
        return {
            "status": "ERROR", 
            "message": "Chave API do Gemini não está configurada. Verifique GEMINI_API_KEY nas configurações."
        }
    
    # URL da API do Gemini (usando modelo atualizado)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    # Prompt do sistema
    system_prompt = """Você é um classificador de catálogo para construção civil. 

Sua tarefa é analisar a descrição de um item e:
1. Se o item se encaixa claramente em uma subcategoria existente (com 95% de certeza), retorne status "EXISTENTE" com os IDs
2. Se o item não se encaixa em nenhuma subcategoria existente, retorne status "SUGERIR_NOVA" com nomes para nova categoria

IMPORTANTE: Responda APENAS em formato JSON válido."""
    
    # Prompt completo
    full_prompt = f"""
CATÁLOGO EXISTENTE:
{categories_list}

REGRAS:
1. Para status "EXISTENTE": retorne categoria_mae_id e subcategoria_id (números)
2. Para status "SUGERIR_NOVA": retorne nova_categoria_mae e nova_subcategoria (textos)
3. Responda APENAS em JSON válido

CLASSIFIQUE O SEGUINTE ITEM: {item_description}

Formato de resposta esperado:
{{
    "status": "EXISTENTE" ou "SUGERIR_NOVA",
    "categoria_mae_id": número (apenas se EXISTENTE),
    "subcategoria_id": número (apenas se EXISTENTE),
    "nova_categoria_mae": "texto" (apenas se SUGERIR_NOVA),
    "nova_subcategoria": "texto" (apenas se SUGERIR_NOVA)
}}
"""
    
    # Dados da requisição
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": full_prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "topK": 1,
            "topP": 0.8,
            "maxOutputTokens": 1024,
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        # Fazer a requisição para a API
        print(f"🔍 Enviando requisição para Gemini API...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"📊 Status da resposta: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Extrair o texto da resposta
            if 'candidates' in result and len(result['candidates']) > 0:
                text_response = result['candidates'][0]['content']['parts'][0]['text']
                print(f"📝 Resposta da API: {text_response}")
                
                try:
                    # Tentar fazer parse do JSON
                    classification_result = json.loads(text_response.strip())
                    
                    # Validar se tem o campo status
                    if 'status' not in classification_result:
                        return {
                            "status": "ERROR",
                            "message": "Resposta da API não contém campo 'status'"
                        }
                    
                    return classification_result
                    
                except json.JSONDecodeError as e:
                    return {
                        "status": "ERROR",
                        "message": f"Erro ao fazer parse do JSON da resposta: {str(e)}. Resposta: {text_response}"
                    }
            else:
                return {
                    "status": "ERROR",
                    "message": "Resposta da API não contém candidatos"
                }
        else:
            error_text = response.text
            print(f"❌ Erro na API: {error_text}")
            return {
                "status": "ERROR",
                "message": f"Erro HTTP {response.status_code}: {error_text}"
            }
            
    except requests.exceptions.Timeout:
        return {
            "status": "ERROR",
            "message": "Timeout na requisição para a API do Gemini"
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "ERROR",
            "message": "Erro de conexão com a API do Gemini"
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Erro inesperado: {str(e)}"
        }

# --- 4. FUNÇÃO DE COMPATIBILIDADE (para não quebrar código existente) ---
# Caso o código antigo tente acessar gemini_model
class GeminiModelCompatibility:
    """Classe de compatibilidade para manter o código antigo funcionando"""
    
    def __init__(self):
        self.is_configured = get_api_key() is not None
    
    def __bool__(self):
        return self.is_configured

# Criar instância para compatibilidade
gemini_model = GeminiModelCompatibility()

# --- 5. FUNÇÃO DE TESTE PARA DEBUG ---
def debug_gemini_service():
    """Função para testar o serviço Gemini"""
    print("🔍 Testando serviço Gemini...")
    
    # Testar conexão
    is_connected, message = test_gemini_connection()
    print(f"📡 Conexão: {'✅ OK' if is_connected else '❌ ERRO'} - {message}")
    
    if is_connected:
        # Testar classificação
        test_description = "Cimento Portland CP-II-E-32"
        test_categories = """
        Categoria Mãe: Materiais Básicos (ID: 1)
        - Subcategoria: Cimento (ID: 1)
        - Subcategoria: Areia (ID: 2)
        - Subcategoria: Brita (ID: 3)
        """
        
        result = classify_item_with_gemini(test_description, test_categories)
        print(f"🧪 Teste de classificação: {result}")
    
    return is_connected

if __name__ == "__main__":
    debug_gemini_service()