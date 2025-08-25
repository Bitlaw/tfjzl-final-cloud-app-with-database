from django.shortcuts import render
from django.http import HttpResponseRedirect
# <HINT> Import any new Models here
# Updated import line to include new models
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))


# *** NEW VIEWS FOR TASK 5 ***
# Helper function to extract selected choices from the request
# Updated to match the example logic and the hint's key format ('choice_')
def extract_answers(request):
    """Extracts selected choice IDs from the submitted exam form."""
    submitted_answers = []
    for key in request.POST:
        # Check if the key starts with 'choice_' (as used in the template)
        if key.startswith('choice_'):
            # The value is the choice ID
            choice_id = int(request.POST[key])
            submitted_answers.append(choice_id)
    return submitted_answers

# <HINT> Create a submit view to create an exam submission record for a course enrollment,
# you may implement it based on following logic:
         # Get user and course object, then get the associated enrollment object created when the user enrolled the course
         # Create a submission object referring to the enrollment
         # Collect the selected choices from exam form
         # Add each selected choice object to the submission object
         # Redirect to show_exam_result with the submission id
def submit(request, course_id):
    """Handles the submission of the exam form and redirects to results."""
    # Get the course object or return a 404 error if not found
    course = get_object_or_404(Course, pk=course_id)
    # Get the currently logged-in user
    user = request.user

    # Get the enrollment record linking the user to the course
    # This assumes one enrollment per user per course
    enrollment = Enrollment.objects.get(user=user, course=course)

    # Create a new, empty submission record linked to this enrollment
    submission = Submission.objects.create(enrollment=enrollment)

    # Extract the list of selected choice IDs from the POST data
    # Note: extract_answers now returns IDs, so we need to get the objects
    selected_choice_ids = extract_answers(request)
    # Get the actual Choice objects from the database using the IDs
    selected_choices = Choice.objects.filter(id__in=selected_choice_ids)

    # Associate the selected Choice objects with the new submission record
    # set() replaces any existing related objects
    submission.choices.set(selected_choices)

    # Get the ID of the newly created submission
    submission_id = submission.id

    # Redirect the user to the exam results page for this submission
    # reverse() generates the URL for the 'exam_result' view with the required arguments
    return HttpResponseRedirect(reverse(viewname='onlinecourse:exam_result', args=(course_id, submission_id,)))


# <HINT> Create an exam result view to check if learner passed exam and show their question results and result for each question,
# you may implement it based on the following logic:
        # Get course and submission based on their ids
        # Get the selected choice ids from the submission record
        # For each selected choice, check if it is a correct answer or not
        # Calculate the total score
def show_exam_result(request, course_id, submission_id):
    """Calculates the exam result and displays it."""
    # Initialize an empty context dictionary for the template
    context = {}

    # Get the course object or return a 404 error if not found
    course = get_object_or_404(Course, pk=course_id)

    # Get the specific submission record using its ID
    submission = Submission.objects.get(id=submission_id)

    # Get all the Choice objects that were selected in this submission
    selected_choices = submission.choices.all()

    # Initialize the learner's total score
    total_score = 0

    # Get all questions associated with the course
    questions = course.question_set.all()

    # Iterate through each question in the course to calculate the score
    for question in questions:
        # --- Scoring Logic using the Question model's method ---
        # Get the choices selected by the user for this specific question
        selected_choices_for_question = selected_choices.filter(question=question)
        # Extract the IDs of the selected choices for this question
        selected_ids = [choice.id for choice in selected_choices_for_question]

        # Use the `is_get_score` method defined in the Question model
        # This checks if the set of selected IDs exactly matches the set of correct IDs
        # for that question.
        if question.is_get_score(selected_ids):
            # If the user selected exactly the correct choices, add the question's grade
            total_score += question.grade
        # --- End Scoring Logic ---

    # Add the calculated data to the context dictionary
    context['course'] = course
    context['grade'] = total_score
    # Pass selected choices if needed in the template
    context['selected_choices'] = selected_choices

    # Render the exam result template, passing the context data
    return render(request, 'onlinecourse/exam_result_bootstrap.html', context)
# *** END NEW VIEWS FOR TASK 5 ***
