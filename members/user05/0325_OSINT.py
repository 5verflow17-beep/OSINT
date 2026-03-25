"""
LockBit 분석 - 개선 버전 / ver. 02_20250325

1 중복 제거 추가 (URL 기준)
2 한국 판별 정확도 향상 (1차/2차 키워드 분리)
3 false positive 방지 (exclude 키워드)
4 키워드 빈도 분석 추가
5 한국 관련 피해자만 별도 저장

"""

import json
from datetime import datetime
from collections import Counter

# 데이터 로드
print("="*60)
print("LockBit 피해자 분석 (중복 제거 + 정확도 개선)")
print("="*60)
print()

with open('OSINT/LockBit/victims_20260321_013004.json', 'r', encoding='utf-8') as f:
    victims = json.load(f)

print(f" 원본 데이터: {len(victims)}개\n")

# ============================================
# 1. 중복 제거 (URL 기준)
# ============================================
seen_urls = set()
unique_victims = []

for v in victims:
    url = v.get('url', '')  # 고유 식별자로 URL 사용
    
    if url and url not in seen_urls:
        seen_urls.add(url)
        unique_victims.append(v)
    elif not url:  # URL 없으면 company_name으로
        name = v.get('company_name', '').lower().strip()
        if name not in seen_urls:
            seen_urls.add(name)
            unique_victims.append(v)

victims = unique_victims
print(f" 중복 제거 후: {len(victims)}개\n")

# ============================================
# 2. 개선된 키워드 (더 정확하게)
# ============================================
keywords = {
    "korea_primary": [  # 1차: 확실한 한국
        ".co.kr", ".go.kr", ".or.kr", ".ac.kr",
        "seoul", "서울", "busan", "부산", 
        "대한민국", "한국", "incheon", "인천",
        "south korea", "republic of korea",
        "gangnam", "강남"
    ],
    "korea_secondary": [  # 2차: 애매한 키워드 (다른 키워드와 조합 필요)
        "korea", "korean",
        "korea corp", "korean company"
    ],
    "industry_specific": [
        "semiconductor", "반도체", "memory chip",
        "automotive", "자동차", "ev battery",
        "shipbuilding", "조선", "steel", "철강",
        "petrochemical", "석유화학", "electronics"
    ],
    "data_types": [
        "customer list", "고객명단", "employee data",
        "source code", "소스코드", "blueprint",
        "financial report", "재무보고서", "contract"
    ],
    "exclude": [  # 제외할 키워드 (false positive 방지)
        "korean bbq", "korean restaurant", "korean food",
        "north korea", "dprk"
    ]
}

# ============================================
# 3. 스마트 매칭 (정확도 향상)
# ============================================
def is_korea_related(victim):
    """한국 관련 여부를 더 정확하게 판단"""
    text = (victim.get('company_name', '') + ' ' + 
            victim.get('description', '') + ' ' +
            victim.get('url', '')).lower()
    
    # 제외 키워드 체크
    for exclude_kw in keywords['exclude']:
        if exclude_kw in text:
            return False, []
    
    matched = []
    
    # 1차 키워드 (확실한 한국) - 이것만 있어도 OK
    for kw in keywords['korea_primary']:
        if kw.lower() in text:
            matched.append(kw)
            return True, matched
    
    # 2차 키워드 (애매한 것) - 다른 한국 키워드랑 같이 있어야 함
    has_secondary = False
    secondary_kw = None
    for kw in keywords['korea_secondary']:
        if kw.lower() in text:
            has_secondary = True
            secondary_kw = kw
            break
    
    # 2차 키워드 + 산업 키워드 조합
    if has_secondary:
        for kw in keywords['industry_specific']:
            if kw.lower() in text:
                matched.append(secondary_kw)
                matched.append(kw)
                return True, matched
    
    return False, []

# ============================================
# 4. 분석 실행
# ============================================
korea_victims = []
industry_related = []
data_related = []

for victim in victims:
    text = (victim.get('company_name', '') + ' ' + 
            victim.get('description', '')).lower()
    
    matched_keywords = []
    categories = []
    
    # 한국 관련 체크 (개선된 로직)
    is_korea, korea_kws = is_korea_related(victim)
    if is_korea:
        categories.append('location_keywords')
        matched_keywords.extend(korea_kws)
        korea_victims.append(victim)
    
    # 산업 키워드
    for kw in keywords['industry_specific']:
        if kw.lower() in text:
            if 'industry_specific' not in categories:
                categories.append('industry_specific')
                industry_related.append(victim)
            matched_keywords.append(kw)
    
    # 데이터 유형
    for kw in keywords['data_types']:
        if kw.lower() in text:
            if 'data_types' not in categories:
                categories.append('data_types')
                data_related.append(victim)
            matched_keywords.append(kw)
    
    victim['matched_keywords'] = list(set(matched_keywords))  # 중복 제거
    victim['matched_categories'] = categories

# ============================================
# 5. 출력 (이전과 동일하게 유지)
# ============================================
print("="*60)
print(f"🇰🇷 한국 관련 피해자: {len(korea_victims)}개")
print("="*60)
print()

for i, v in enumerate(korea_victims, 1):
    print(f"[{i}] {v.get('company_name', 'N/A')}")
    
    if v.get('matched_keywords'):
        korea_kws = [k for k in v['matched_keywords'] 
                     if k in keywords['korea_primary'] + keywords['korea_secondary']]
        if korea_kws:
            print(f"     키워드: {', '.join(korea_kws)}")
    
    if v.get('description'):
        desc = v['description'].replace('\n', ' ')[:100]
        print(f"     {desc}...")
    
    if v.get('deadline'):
        print(f"     {v['deadline']}")
    
    if v.get('url'):
        print(f"     {v['url']}")
    
    print()

# 통계
print("="*60)
print(" 통계")
print("="*60)
print(f"전체 피해자: {len(victims)}개")
print()
print(f"KOREA 한국 관련: {len(korea_victims)}개 ({len(korea_victims)/len(victims)*100:.1f}%)")
print(f" 주요 산업: {len(industry_related)}개 ({len(industry_related)/len(victims)*100:.1f}%)")
print(f" 민감 데이터: {len(data_related)}개 ({len(data_related)/len(victims)*100:.1f}%)")

# 다중 카테고리 매칭
multi_match = [v for v in victims if len(v.get('matched_categories', [])) >= 2]
print(f" 다중 매칭: {len(multi_match)}개")

if multi_match:
    print("\n 주요 다중 매칭 (한국 관련):")
    korea_multi = [v for v in multi_match if 'location_keywords' in v.get('matched_categories', [])]
    for v in korea_multi[:5]:
        cats = v['matched_categories']
        print(f"  - {v.get('company_name', 'N/A')}: {', '.join(cats)}")

# 키워드 빈도 분석 (추가)
print("\n 가장 많이 탐지된 키워드 (한국 관련):")
all_keywords = []
for v in korea_victims:
    all_keywords.extend(v.get('matched_keywords', []))

keyword_counts = Counter(all_keywords)
for kw, count in keyword_counts.most_common(10):
    print(f"  {kw}: {count}회")

# 저장
output_data = {
    'analysis_date': datetime.now().isoformat(),
    'total_victims': len(victims),
    'korea_related': len(korea_victims),
    'victims': victims,
    'korea_victims_only': korea_victims  # 한국 관련만 따로
}

with open('analyzed.json', 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

# 한국 관련만 별도 저장
with open('korea_victims.json', 'w', encoding='utf-8') as f:
    json.dump(korea_victims, f, ensure_ascii=False, indent=2)

print(f"\n 분석 완료!")
print(f" 저장: analyzed.json, korea_victims.json")