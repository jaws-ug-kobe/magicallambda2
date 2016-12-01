from __future__ import print_function

import boto3
import urllib2
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')


def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': "SessionSpeechlet - " + title,
            'content': "SessionSpeechlet - " + output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }


def update_history(base_history, new_history):
    base_history.append(new_history)
    return base_history


def get_com_answer(history, player_answer):
    table = dynamodb.Table('magical_lambda_words')
    print(player_answer)
    try:
        response = table.query(
          KeyConditionExpression=Key('word').eq(player_answer)
        )
    except:
        print("Word not found error #{player_answer}")

    print(response)
    if response['Count'] is 0:
        return None
    else:
        ng_words = [w['word'] for w in history]
        answer_candidates = [w for w in response['Items'][0]['values'] if not w in ng_words]
        print(answer_candidates)
        return answer_candidates[0] if len(answer_candidates) > 0 else None


def get_welcome_response():

    session_attributes = {}
    card_title = "Welcome"
    speech_output = "Welcome to the Magical Lambda. " \
                    "You must do the imagination game with me, " \
                    "You must imagin a word from a word I said" \
                    "The first word banana" \

    history = update_history([], {"type": "com", "word": "banana", "count": 1})
    session_attributes["history"] = history

    reprompt_text = "Let imagine a word from banana."
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def handle_session_end_request():
    card_title = "Session Ended"
    speech_output = "Thank you for trying the Magical Lambda. "
    should_end_session = True
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, should_end_session))


def memory_player_answer(key, new_word):
    table = dynamodb.Table('magical_lambda_words')
    item = table.get_item(Key={'word':key})
    print(item)
    if item:
        item['Item']['values'] = item['Item']['values'].append(new_word)
        table.update_item(
            key={'word':key}, 
            UpdateExpression='SET values = :val1', 
            ExpressionAttributeValues={':val1': item['Item']['values']})
    else:
        table.put_item(Item={'word':key, 'values':[new_word]})
        
    return True


def associatable(from_word, to_word):
    return True

def accept_player_voice(intent, session):
    card_title = 'MagicalLambdaAcceptIntent::Accept'
    session_attributes = {}
    should_end_session = False

    if 'Answer' in intent['slots']:
        player_answer = intent['slots']['Answer']['value']
        speech_output = "Your answer is " + player_answer + "yes, if you ok, no, say again"
        reprompt_text = "Please yes or answer again"
        session_attributes["Answer"] = player_answer
        session_attributes["history"] = session['attributes']['history']
        
    else:
        speech_output = "I'm not sure what your a word is. Please try again."
        reprompt_text = "I'm not sure what your a woad is. "

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))

def respond_from_com(intent, session):

    card_title = 'MagicalLambdaAnswerIntent::Answer'
    session_attributes = {}
    should_end_session = False

    if 'Confirm' in intent['slots']:
        player_respond = intent['slots']['Confirm']['value']
        if player_respond == 'yes':
            player_answer = session['attributes']['Answer']
            history = session['attributes']['history']

            previous_word = history[-1]["word"] if history[-1]["type"] == 'com' else None

            if previous_word is None:
                raise ValueError("Game could not proceeding.")

            if associatable(previous_word, player_answer):
                com_answer = get_com_answer(history, player_answer)
                if com_answer is None:
                    speech_output = "I can not imagin a associated word from a " + player_answer + "I lose. you have strong imagination. Please tell associated word."
                    reprompt_text = ""
                    session_attributes["Answer"] = player_answer
                    should_end_session = False
                else:
                    speech_output = "Your a word is " + player_answer + "." + "I imagined a " + com_answer + "." + " Please say next word."
                    reprompt_text = "Please imagin a word from " + com_answer
                    recently_player_answer = {"type":"player", "word":player_answer, "count":len(history)+1}
                    recentry_com_answer = {"type":"com", "word":com_answer, "count":len(history)+2}
                    history = update_history(history, recently_player_answer)
                    history = update_history(history, recentry_com_answer)
                    session_attributes["history"] = history

            else:
                speech_output = "Your answer is not associatable from #{previous_word}. You lose."
                reprompt_text = ""
                should_end_session = True
    else:
        speech_output = "I'm not sure what your a word is. Please try again."
        reprompt_text = "I'm not sure what your a woad is. "

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def respond_to_teach(intent, session):
    card_title = 'MagicalLambdaTeachIntent::Teach'
    session_attributes = {}
    should_end_session = True

    if 'Word' in intent['slots']:
        keyword = session['attributes']['Answer']
        associated_word = intent['slots']['Word']
        memory_player_answer(keyword, associated_word)
        speech_output = "I remembered. Thank you."
        reprompt_text = "Please teach again"
    else:
        speech_output = "I'm not sure what your a word is. Please try again."
        reprompt_text = "I'm not sure what your a woad is. "

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))
   
def on_session_started(session_started_request, session):
    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    return get_welcome_response()


def on_intent(intent_request, session):
    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    if intent_name == "MagicalLambdaAcceptIntent":
        return accept_player_voice(intent, session)
    elif intent_name == "MagicalLambdaAnswerIntent":
        return respond_from_com(intent, session)
    elif intent_name == "MagicalLambdaTeachIntent":
        return respond_to_teach(intent, session)
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])


def lambda_handler(event, context):
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])
