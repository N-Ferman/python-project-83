def get_seo_data(soup):
    title = ''
    h1 = ''
    description = ''

    if soup.title:
        title = soup.title.get_text(strip=True)

    if soup.h1:
        h1 = soup.h1.get_text(strip=True)

    description_tag = soup.find('meta', attrs={'name': 'description'})
    if description_tag:
        description = description_tag.get('content', '')

    return {
        'title': title,
        'h1': h1,
        'description': description,
    }