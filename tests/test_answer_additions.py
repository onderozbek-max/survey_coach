"""Missing answers are additive edits, never replacement question wording."""
from copy import deepcopy

from surveycoach.recommendations import guard_recommendation
from surveycoach.server.rounds import change_sheet
from surveycoach.server.report import summary_packet

STEM = 'How did you shop for seasonal items? Check all that apply.'
ANSWERS = ['In club', 'Online delivery', 'Store pickup']
ADDITION = 'I did not shop for seasonal items this year'
SNAPSHOT = {'pages':[{'id':'p1','questions':[{'id':'q1','text':STEM,
    'kind':'multi_choice','options':[{'label':text} for text in ANSWERS]}]}]}


def bundled():
    return {'criterion_id':'B2','source':'ai','severity':'must_fix','question_id':'q1','page_id':'p1',
        'headline':'Nonshoppers have no answer','evidence':STEM,'member_impact':'Cannot answer honestly.',
        'explanation':'Add an answer for nonshoppers.','structural':True,'fingerprint':'stable',
        'current_text':'\n'.join([STEM,*ANSWERS]),
        'suggested_text':'\n'.join([STEM+' If you did not shop, select only that answer.',*ANSWERS,ADDITION]),
        'options':[{'label':'Neutral','text':'\n'.join([STEM,*ANSWERS,ADDITION])},
                   {'label':'Shorter','text':'\n'.join(['Which ways did you shop?',*ANSWERS,ADDITION])}]}


def test_bundle_becomes_precise_add_answer_without_rewriting_stem():
    original=bundled(); before=deepcopy(original)
    result=guard_recommendation(original,SNAPSHOT)
    assert result['edit_kind']=='add_answer'
    assert result['suggested_text']==ADDITION
    assert result['options']==[{'label':'Add answer option','text':ADDITION}]
    assert result['structural'] is True
    assert 'exclusive' in result['explanation'].lower()
    assert 'Keep the question' in result['explanation']
    assert result['fingerprint']=='stable' and result['evidence']==STEM
    assert original==before
    assert guard_recommendation(result,SNAPSHOT)==result


def test_changed_or_removed_existing_answers_are_not_misclassified_as_additions():
    original=bundled()
    original['suggested_text']='\n'.join([STEM,'In club','Delivery',ADDITION])
    original['options']=[]
    result=guard_recommendation(original,SNAPSHOT)
    assert result.get('edit_kind')!='add_answer'


def test_existing_answer_and_unmatched_locations_are_not_invented_additions():
    original=bundled(); original['question_id']='missing'
    assert guard_recommendation(original,SNAPSHOT).get('edit_kind')!='add_answer'


def test_signoff_and_server_change_sheet_label_addition_not_replacement():
    finding=guard_recommendation(bundled(),SNAPSHOT)
    snapshot=deepcopy(SNAPSHOT); snapshot['pages'][0]['position']=0
    detail={'snapshot':snapshot,'title':'Synthetic','version':1,'review':{'findings':[finding],
        'scorecard':{'score':0,'unchecked_points':100}},
        'decisions':{'stable':{'action':'pick','picked_text':ADDITION}}}
    lines=change_sheet(detail)
    assert lines[0]['target']=='New answer option'
    assert lines[0]['edit_kind']=='add_answer'
    packet=summary_packet(detail)
    assert 'Add answer option:' in packet
    assert 'Replace:' not in packet


def test_generic_addition_does_not_invent_exclusivity():
    original=bundled()
    original['suggested_text']='\n'.join([STEM,*ANSWERS,'At a temporary stall'])
    original['options']=[]
    result=guard_recommendation(original,SNAPSHOT)
    assert result['edit_kind']=='add_answer'
    assert result['suggested_text']=='At a temporary stall'
    assert 'exclusive' not in result['explanation'].lower()
