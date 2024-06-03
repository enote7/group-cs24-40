from django.shortcuts import redirect, render
from django.conf import settings
from django.core.mail import send_mail
from .forms import *
from .models import *
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
import random
import time
from agora_token_builder import RtcTokenBuilder
from .models import RoomMember
import json
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from .forms import AdminStaffNumberForm


User = get_user_model()

def is_superuser(user):
    return user.is_superuser

def add_admin_staff_number(request):
    if not request.user.is_superuser:
        return HttpResponse("Permission denied")
    if request.method == 'POST':
        form = AdminStaffNumberForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')  # Redirect to the same page after saving
    else:
        form = AdminStaffNumberForm()
    return render(request, 'staff_no.html', {'form': form})


def index (request):
    return render(request, 'index.html')

@login_required
def home (request):
    return render(request, 'home.html')

# SIGNUP
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password1'])
            user_type = form.cleaned_data['user_type']
            if user_type == 'otheruser':
                user.is_other_user = True
            elif user_type == 'adminstaff':
                admin_staff_number = form.cleaned_data['admin_staff_number']
                if not AdminStaffNumber.objects.filter(number=admin_staff_number).exists():
                    messages.error(request, 'Invalid Admin Staff Number.')
                    return render(request, 'signup.html', {'form': form})
                user.is_admin_staff = True
            user.save()
            send_confirmation_email(request, user)  # Send confirmation email
            messages.success(request, 'Please check your email to confirm your account.')
            return redirect('login')
    else:
        form = SignupForm()
    return render(request, 'signup.html', {'form': form})

def send_confirmation_email(request, user):
    token = default_token_generator.make_token(user)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    confirmation_link = request.build_absolute_uri(reverse('confirm_email', kwargs={'uidb64': uidb64, 'token': token}))
    subject = 'Confirm your email address'
    message = f"Please click the following link to confirm your email address: {confirmation_link}"
    send_mail(subject, message, 'enote7y@gmail.com', [user.email])

@csrf_exempt  # Assuming you're using csrf_exempt for specific reasons
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user is not None:
                if user.email_confirmed:
                    login(request, user)
                    # Check user type and redirect accordingly
                    if user.is_admin_staff:
                        return redirect('home')  # Redirect for Other User
                    elif user.is_other_user:
                        return redirect('home')  # Redirect for Admin Staff
                    else:
                        messages.error(request, 'Invalid user type.')
                else:
                    messages.error(request, 'Please confirm your email address to log in.')
            else:
                # Pass error message to the form
                form.add_error(None, 'Invalid email or password. Please try again.')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})

# EMAIL CONFIRMATION
def confirm_email(request, uidb64, token):
    try:
        uid = str(urlsafe_base64_decode(uidb64), 'utf-8')
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.email_confirmed = True
        user.save()
        return render(request, 'email_confirmed.html')
    else:
        return render(request, 'email_confirmation_invalid.html')

def email_confirmation(request):
    return render(request, 'confirmation_email.html')

def email_confirmed(request):
    return render(request, 'email_confirmed.html')

def email_confirmation_invalid(request):
    return render(request, 'email_confirmation_invalid.html')


# PASSWORD RESET
def send_password_reset_email(request, email):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, 'User with this email does not exist.')
        return None

    token = default_token_generator.make_token(user)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = request.build_absolute_uri(reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token}))
    email_subject = 'Password Reset'
    email_body = render_to_string('password_reset_email.html', {'reset_url': reset_url})
    send_mail(email_subject, email_body, 'enote7y@gmail.com', [email])

def csrf_failure_view(request, reason=""):
    return render(request, 'csrf_failure.html', {'reason': reason})

def logout_view(request):
    logout(request)
    return redirect('index')


# Create your views here.

@login_required
def lobby(request):
    return render(request, 'base/lobby.html')

@login_required
def room(request):
    return render(request, 'base/room.html')


def getToken(request):
    appId = "5fd2190de1bc43fcbe2bbce8ef8c5a07"
    appCertificate = "bdec36faade54e80b109743475a93ae9"
    channelName = request.GET.get('channel')
    uid = random.randint(1, 230)
    expirationTimeInSeconds = 3600
    currentTimeStamp = int(time.time())
    privilegeExpiredTs = currentTimeStamp + expirationTimeInSeconds
    role = 1

    token = RtcTokenBuilder.buildTokenWithUid(appId, appCertificate, channelName, uid, role, privilegeExpiredTs)

    return JsonResponse({'token': token, 'uid': uid}, safe=False)


@csrf_exempt
def createMember(request):
    data = json.loads(request.body)
    member, created = RoomMember.objects.get_or_create(
        name=data['name'],
        uid=data['UID'],
        room_name=data['room_name']
    )

    return JsonResponse({'name':data['name']}, safe=False)


def getMember(request):
    uid = request.GET.get('UID')
    room_name = request.GET.get('room_name')

    member = RoomMember.objects.get(
        uid=uid,
        room_name=room_name,
    )
    name = member.name
    return JsonResponse({'name':member.name}, safe=False)

@csrf_exempt
def deleteMember(request):
    data = json.loads(request.body)
    member = RoomMember.objects.get(
        name=data['name'],
        uid=data['UID'],
        room_name=data['room_name']
    )
    member.delete()
    return JsonResponse('Member deleted', safe=False)


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from vidstream import ScreenShareClient
import threading
from .models import RoomMember

def start_screen_share(request, room_name):
    # Get all members in the room
    room_members = RoomMember.objects.filter(room_name=room_name)
    # Start screen sharing for each member in the room
    for member in room_members:
        sender = ScreenShareClient(member.uid, 9999)  # Use member's UID as IP
        t = threading.Thread(target=sender.start_stream)
        t.start()
    return JsonResponse({'message': 'Screen sharing started successfully for the room!'})

def stop_screen_share(request, room_name):
    # Get all members in the room
    room_members = RoomMember.objects.filter(room_name=room_name)
    # Stop screen sharing for each member in the room
    for member in room_members:
        sender = ScreenShareClient(member.uid, 9999)  # Use member's UID as IP
        sender.stop_stream()
    return JsonResponse({'message': 'Screen sharing stopped successfully for the room!'})



def chatindex(request):
    return render(request, "base/chatindex.html")


def chatroom(request, room_name):
    return render(request, "base/chatroom.html", {"room_name": room_name})


def send_emails(email_addresses, subject, message):
    for email in email_addresses:
        if email:
            send_mail(subject, message, 'enote7y@gmail.com', [email])

def email_view(request):
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            email_addresses = [
                form.cleaned_data.get('email1'),
                form.cleaned_data.get('email2'),
                form.cleaned_data.get('email3'),
            ]
            chat_name = form.cleaned_data.get('chat_name')
            conference_name = form.cleaned_data.get('conference_name')
            rules = form.cleaned_data.get('rules')

            # Customize the email message to include chat name, conference name, and rules
            chat_message = f"You are invited to a chatting conversation --->\n\n\n NAME:\n\n '\n {chat_name} \n\n'\n\n RULES:\n\n '\n {rules} \n\n'\nmgt😊 \n \n you can follow this link to join \n http://127.0.0.1:8000/chatindex/ \n"
            conference_message = f"You are invited to a conference Meeting --->\n\n\n NAME:\n\n '\n{conference_name}\n\n' RULES:\n\n {rules}\n\n \nDON'T FORGET YOUR NAMES BELOW \nmgt😊 \n \n you can follow this link to join \n http://127.0.0.1:8000/ \n"

            if 'start_chat' in request.POST:
                send_emails(email_addresses, 'Chat Invitation', chat_message)
                return redirect('chatindex')
            elif 'start_conference' in request.POST:
                send_emails(email_addresses, 'Conference Invitation', conference_message)
                return redirect('lobby')
    else:
        form = EmailForm()
    return render(request, 'email_form.html', {'form': form})


def upload(request):
    if not request.user.is_staff:
        return HttpResponse("Permission denied")
    if request.method == 'POST':
        form = AttendeeForm(request.POST, request.FILES)
        if form.is_valid():
            attendee = form.save(commit=False)
            attendee.user = request.user
            attendee.room_name = form.cleaned_data['room_name']
            attendee.save()
            return redirect('upload')
    else:
        form = AttendeeForm()

    return render(request, 'upload.html', {'form': form})

@login_required
def download_video(request, video_id):
    attendee = get_object_or_404(Attendee, id=video_id)
    video_file = attendee.recorded_video

    response = HttpResponse(video_file, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename={video_file.name}'
    
    return response

@login_required
def video_list(request):
    query = request.GET.get('room_name')
    if query:
        videos = Attendee.objects.filter(room_name__icontains=query)
    else:
        videos = Attendee.objects.none()  # No videos displayed initially
    return render(request, 'video_list.html', {'videos': videos})



@login_required
def aboutus(request):
    return render(request, 'aboutus.html')


@login_required
def contactus(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.user = request.user
            question.save()
            messages.success(request, 'Thank you for your question. We will get back to you with your answer tagged in one of our platforms😉!')
            return redirect('home')
    else:
        form = QuestionForm()

    return render(request, 'contactus.html', {'form': form})


@login_required
def admin_dashboard(request, question_id=None):
    if not request.user.is_staff:
        return HttpResponse("Permission denied")

    unanswered_questions = Question.objects.filter(answers__isnull=True)

    current_question = None
    form = None

    if question_id:
        current_question = get_object_or_404(Question, pk=question_id)
        if request.method == 'POST':
            form = AnswerForm(request.POST)
            if form.is_valid():
                answer = form.save(commit=False)
                answer.user = request.user
                answer.question = current_question
                answer.save()
                messages.success(request, 'Your answer has been submitted.')
                return redirect('admin_dashboard')
        else:
            form = AnswerForm()

    return render(request, 'admin_dashboard.html', {
        'unanswered_questions': unanswered_questions,
        'current_question': current_question,
        'form': form
    })

@login_required
def all_answers(request):
    all_answers = Answer.objects.select_related('question').all()
    return render(request, 'all_answers.html', {'all_answers': all_answers})
