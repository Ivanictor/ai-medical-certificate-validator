from rapidfuzz import fuzz

#Código do Gabriel Mesquita para determinar a similaridade dos nomes

def compare_names(name1, name2):
    # Similaridade usando Levenshtein Distance
    levenshtein_score = fuzz.ratio(name1.lower(), name2.lower())
    
    # Similaridade usando Jaro-Winkler (melhor para nomes)
    jaro_winkler_score = fuzz.WRatio(name1.lower(), name2.lower())
    
    # Média ponderada das similaridades
    final_score = (levenshtein_score * 0.5) + (jaro_winkler_score * 0.5)
    
    return {"similarity": final_score / 100,
            "levenshtein_score": levenshtein_score/100,
            "jaro_winkler_score": jaro_winkler_score/100}
