"""Idempotent editorial projection for both repository and persistent catalogs.

Never deletes, reorders or renumbers source records. Headlines remain stable
for historical learning; editorial angles supply the new presentation.
"""
import copy
import re

REVISION = 'us-prospecting-2026-09-v1'
USGS = 'https://www.usgs.gov/faqs/what-fools-gold'
PANNING = 'https://www.fs.usda.gov/Internet/FSE_DOCUMENTS/stelprdb5274730.pdf'
MARKETING = re.compile(r'high.engagement outliers|viral content|viral blueprint|high.converting|trigger the algorithm|grow your prospecting brand|optimize your metadata|maximum audience dopamine', re.I)


def allowed(topic):
    text = ' '.join(str(topic.get(k,'')) for k in ('headline','subtitle','list_points'))
    return not topic.get('retired') and not MARKETING.search(text)


# Keys are headlines, never numeric IDs: production and repository IDs differ.
REVISIONS = {
    'GOLD VS PYRITE': ('Is It Gold, Pyrite, or Mica? What a Photo Cannot Prove', [
        'Pyrite, chalcopyrite and weathered mica can resemble gold.',
        'Appearance in a picture is a clue, not a confirmed identification.',
        'Gold is malleable; brittle look-alikes behave differently under appropriate physical tests.',
        'For uncertain or valuable specimens, seek qualified identification rather than a confident photo diagnosis.'
    ], USGS),
    'BLACK SAND SECRETS': ('Black Sand but No Gold: What Should You Check Next?', [
        'Black sands can contain several heavy minerals, not only magnetite.',
        'Magnetic separation does not identify every mineral in the remaining concentrate.',
        'Black sand is a reason to sample, not proof of gold.',
        'Keep samples labeled and compare observations before drawing a conclusion.'
    ], PANNING),
    'NO GOLD FOUND': ('No Gold Yet: Compare Your Samples Before Blaming Your Technique', [
        'An empty test pan can reflect location, sampling variation or technique.',
        'Compare similarly sized samples and record where they came from.',
        'Check technique using retained practice material in a collecting tub.',
        'Neither quartz nor black sand guarantees a productive deposit.'
    ], PANNING),
    'FINE GOLD RECOVERY': ('Fine Gold Cleanup: Why the Last Spoonful Is Difficult', [
        'Separate initial concentration from the slower final cleanup.',
        'Work with manageable portions and retain material for rechecking.',
        'Compare mechanical cleanup methods appropriate to particle size and equipment.',
        'Do not recommend mercury, chemical extraction or guaranteed recovery percentages.'
    ], PANNING),
    'SAMPLING STRATEGIES': ('Two Sample Spots, Same Amount of Material: How to Compare Fairly', [
        'Label each location and compare similar sample volumes.',
        'Use a consistent panning method and note sampling conditions.',
        'Record observed gold separately from other heavy minerals.',
        'Two pans are an initial comparison, not proof of a continuous or economic paystreak.'
    ], PANNING),
    'SLUICE BOXES': ('Your Sluice Is Packing Up: What to Observe Before Adjusting It', [
        'Observe material movement, feed consistency and buildup.',
        'Use setup guidance for the specific sluice rather than one universal angle.',
        'Change one setting at a time and compare retained output material.',
        'A small test cannot establish perfect recovery or guaranteed yield.'
    ], PANNING),
    'DETECTOR GROUND BALANCE': ('Ground Balance: Follow Your Detector and Site Conditions', [
        'Mineralized ground can affect detector response.',
        'Follow the manual for the specific detector and ground-balance mode.',
        'Check the response on appropriate test ground before interpreting targets.',
        'Do not claim manual balance always outperforms automatic balance.'
    ], None),
    'TAILINGS': ('Old Tailings Are a Sampling Question, Not Guaranteed Gold', [
        'Historical recovery methods and deposits differed.',
        'Do not assume all older equipment missed fine gold.',
        'Compare documented samples before claiming material has recoverable gold.',
        'New equipment alone does not establish that a site is productive.'
    ], None),
    'BEDROCK TRAPS': ('Bedrock Cracks: Places to Test, Not Promises of Gold', [
        'Describe cracks, depressions and rough bedrock as possible physical traps.',
        'Explain the local geometry without inventing chemical-trap mechanisms.',
        'Compare small accessible samples and record the observations.',
        'A promising shape does not establish gold presence.'
    ], PANNING),
}

ADDITIONS = [
    {'id':10001,'curation_key':'sluice-output-check','headline':'CHECK YOUR SLUICE TAILINGS',
     'subtitle':'Check retained output before guessing whether gold is being lost.',
     'list_header':'A PRACTICAL CHECK', 'list_points':[
         'Collect a manageable representative portion of processed output for checking.',
         'Keep test material labeled so different settings are not mixed.',
         'Change one setting at a time, following the equipment manual.',
         'A limited test does not establish a recovery percentage or perfect capture.'],
     'research_source':'https://www.reddit.com/r/Prospecting/comments/1w4rpzp/looking_for_good_sluice_box_recommendations_for/'},
    {'id':10002,'curation_key':'home-panning-practice','headline':'PRACTICE PANNING IN A CATCH TUB',
     'subtitle':'Practice with retained material instead of losing track of your mistakes.',
     'list_header':'PRACTICE AND RECHECK', 'list_points':[
         'Use a stable collecting tub so practice material can be recovered.',
         'Work with manageable portions and repeat the same technique.',
         'Recheck collected material to understand what was washed out.',
         'Do not release practice material into streams or equate practice success with finding a deposit.'],
     'research_source':'https://www.reddit.com/r/Prospecting/comments/1hiwmrm/'}
]


def curate(topics):
    result = copy.deepcopy(topics)
    ids = [t['id'] for t in result]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate topic IDs: reconcile before loading catalog')
    seen = {}
    for topic in result:
        title = topic.get('headline','').strip().casefold()
        if MARKETING.search(' '.join(str(topic.get(k,'')) for k in ('headline','subtitle','list_points'))):
            topic.update(retired=True, retired_reason='Tema strategi kreator, bukan edukasi prospecting')
        if title in seen:
            topic.update(retired=True, canonical_topic_id=seen[title], retired_reason='Judul duplikat; riwayat dipertahankan')
        elif not topic.get('retired'):
            seen[title]=topic['id']
        revision=REVISIONS.get(topic.get('headline','').upper())
        if revision:
            angle,points,source=revision
            topic.update(editorial_angle=angle, subtitle=angle, list_points=points,
                         list_header='OBSERVE, TEST, AND COMPARE')
            if source:
                topic['reference_url']=source
        if topic.get('id')==999 and 'MINI-GAME' in topic.get('headline',''):
            topic['list_points']=['Inspect the labeled illustration.',
                                  'Explain which visual clue you noticed.',
                                  'Include the explanation in this post.',
                                  'An illustration cannot confirm a real mineral specimen.']
        topic['catalog_revision']=REVISION
    for addition in ADDITIONS:
        if any(t.get('curation_key')==addition['curation_key'] for t in result):
            continue
        new=copy.deepcopy(addition)
        if new['id'] in ids:
            new['id']=max(ids)+1
        new['catalog_revision']=REVISION
        new['experimental_topic']=True
        result.append(new); ids.append(new['id'])
    return result


def remap_state(state, old_topics, active_topics):
    old_ids=state.get('catalog_ids') or [t['id'] for t in old_topics]
    new_ids=[t['id'] for t in active_topics]
    lookup={tid:i for i,tid in enumerate(new_ids)}
    def mapped(index):
        if isinstance(index,int) and 0<=index<len(old_ids):
            return lookup.get(old_ids[index])
        return None
    state=dict(state)
    state['current_topic_index']=mapped(state.get('current_topic_index',0)) or 0
    state['recently_used']=[v for i in state.get('recently_used',[]) if (v:=mapped(i)) is not None]
    state['catalog_ids']=new_ids
    return state


def load_catalog(path):
    """Apply the same policy to a persistent volume, with an atomic backup."""
    import json
    import os
    import shutil
    import tempfile
    from datetime import datetime, timezone
    from core.locks import ProcessLock
    with ProcessLock('topic-catalog') as lock:
        original=json.loads(path.read_text(encoding='utf-8'))
        updated=curate(original)
        if updated!=original and lock.acquired:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            shutil.copy2(path, path.with_name(path.name+'.backup_'+stamp))
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                                 prefix='.topics-',suffix='.tmp',delete=False) as output:
                    temporary=output.name
                    json.dump(updated,output,indent=4,ensure_ascii=False)
                    output.flush(); os.fsync(output.fileno())
                os.replace(temporary,path)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
        return original,updated
