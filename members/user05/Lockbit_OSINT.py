"""
LockBit 분석 - 카테고리별 키워드 매칭 버전 / ver. 01_20260325
"""

import json
from datetime import datetime

# 데이터 로드
print("="*60)
print("LockBit 피해자 분석")
print("="*60)
print()

with open('victims_20260321_013004.json', 'r', encoding='utf-8') as f:  # 임의의 크롤링 파일 사용(날짜 260321) 추후 업데이트
    victims = json.load(f)

print(f" 총 {len(victims)}개 분석\n")

# 키워드 정의 (임의로 수정, k- 로 들어간 타 국가 기업이 포함됨)
keywords = {
    "location_keywords": [
        # 명확한 한국 키워드만
        "korea", "korean", "south korea", "대한민국", "한국",
        "seoul", "서울", "busan", "부산", "incheon", "인천",
        "gangnam", "강남", "hongdae", "홍대",
        "korean company", "korea corp", "한국 기업", "한국 회사",
        "seoul company", "busan company",
        # 도메인 (더 명확하게)
        ".co.kr", ".go.kr", ".or.kr", ".ac.kr",
        # 삭제: "k-", "korea-", ".kr", "asia pacific" (광범위)
    ],
    "industry_specific": [
        "semiconductor", "반도체", "memory chip", "메모리",
        "automotive", "자동차", "ev battery", "전기차 배터리",
        "shipbuilding", "조선", "steel", "철강",
        "petrochemical", "석유화학", "electronics", "전자"
    ],
    "data_types": [
        "customer list", "고객명단", "employee data", "직원정보",
        "source code", "소스코드", "blueprint", "설계도",
        "financial report", "재무보고서", "contract", "계약서"
    ]
}

# 분석
for victim in victims:
    text = (victim['company_name'] + ' ' + victim['description']).lower()
    
    matched = []
    categories = []
    
    # 각 카테고리별로 키워드 검사
    for category, keyword_list in keywords.items():
        for kw in keyword_list:
            if kw.lower() in text:
                if category not in categories:
                    categories.append(category)
                    matched.append(kw)
                    break
    
    victim['matched_keywords'] = matched
    victim['matched_categories'] = categories

# 필터링
korea_related = [v for v in victims if 'location_keywords' in v.get('matched_categories', [])]
industry_related = [v for v in victims if 'industry_specific' in v.get('matched_categories', [])]
data_related = [v for v in victims if 'data_types' in v.get('matched_categories', [])]

# 출력 - 한국 관련
print("="*60)
print(f"🇰🇷 한국 관련 피해자: {len(korea_related)}개")
print("="*60)
print()

for i, v in enumerate(korea_related, 1):  # 전체 출력
    print(f"[{i}] {v['company_name']}")
    
    if v['matched_keywords']:
        kws = [k for k in v['matched_keywords'] if k in keywords['location_keywords']]
        if kws:
            print(f"    키워드: {kws[0]}")
    
    if v['description']:
        desc = v['description'].replace('\n', ' ')[:100]
        print(f"    {desc}...")
    
    if v['deadline']:
        print(f"     {v['deadline']}")
    
    print()

# 출력 - 산업별
print("="*60)
print(f" 주요 산업 관련 피해자: {len(industry_related)}개")
print("="*60)
print()

for i, v in enumerate(industry_related[:10], 1):
    print(f"[{i}] {v['company_name']}")
    
    if v['matched_keywords']:
        kws = [k for k in v['matched_keywords'] if k in keywords['industry_specific']]
        if kws:
            print(f"    키워드: {', '.join(kws)}")
    
    if v['description']:
        desc = v['description'].replace('\n', ' ')[:70]
        print(f"    {desc}...")
    
    print()

# 출력 - 데이터 유형
print("="*60)
print(f" 민감 데이터 관련: {len(data_related)}개")
print("="*60)
print()

for i, v in enumerate(data_related[:10], 1):
    print(f"[{i}] {v['company_name']}")
    
    if v['matched_keywords']:
        kws = [k for k in v['matched_keywords'] if k in keywords['data_types']]
        if kws:
            print(f"    데이터: {', '.join(kws)}")
    
    if v['description']:
        desc = v['description'].replace('\n', ' ')[:50]
        print(f"    {desc}...")
    
    print()

# 통계
print("="*60)
print(" 통계")
print("="*60)
print(f"전체 피해자: {len(victims)}개")
print()
print(f"🇰🇷 한국 관련: {len(korea_related)}개 ({len(korea_related)/len(victims)*100:.1f}%)")
print(f" 주요 산업: {len(industry_related)}개 ({len(industry_related)/len(victims)*100:.1f}%)")
print(f" 민감 데이터: {len(data_related)}개 ({len(data_related)/len(victims)*100:.1f}%)")

# 중복 (여러 카테고리 매칭)
multi_match = [v for v in victims if len(v.get('matched_categories', [])) >= 2]
print(f"  다중 매칭: {len(multi_match)}개")

if multi_match:
    print("\n주요 다중 매칭:")
    for v in multi_match[:5]:
        cats = v['matched_categories']
        print(f"  - {v['company_name']}: {', '.join(cats)}")

# 저장
with open('analyzed.json', 'w', encoding='utf-8') as f:
    json.dump(victims, f, ensure_ascii=False, indent=2)

print(f"\n 분석 완료!")
print(f" 저장: analyzed.json")