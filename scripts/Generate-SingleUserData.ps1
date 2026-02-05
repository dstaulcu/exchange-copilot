<#
.SYNOPSIS
    Generates Exchange/AD mock data centered around a single "protagonist" user.
    
.DESCRIPTION
    Creates realistic email and meeting data where:
    - All inbox emails are TO the protagonist FROM colleagues
    - All sent emails are FROM the protagonist TO colleagues
    - All meetings include the protagonist as organizer or attendee
    - Colleagues are people the protagonist interacts with
    
.PARAMETER OutputPath
    Path to output the JSON data file.
    
.PARAMETER UserEmail
    Email address for the protagonist user.
    
.PARAMETER UserName
    Display name for the protagonist user.
#>

param(
    [string]$OutputPath = ".\data\exchange_mcp.json",
    [string]$UserEmail = "me@dataflow.local",
    [string]$UserName = "Alex Chen",
    [string]$UserDepartment = "Data Engineering",
    [string]$UserTitle = "Senior Data Engineer",
    [int]$ColleagueCount = 50,
    [int]$InboxEmailCount = 200,
    [int]$SentEmailCount = 100,
    [int]$MeetingCount = 80
)

$ErrorActionPreference = "Stop"

# Source the mock data generator
. "$PSScriptRoot\..\src\utils\MockDataGenerator.ps1"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Single-User Exchange Data Generator" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Protagonist: $UserName <$UserEmail>" -ForegroundColor Green
Write-Host "Department:  $UserDepartment" -ForegroundColor Green
Write-Host "Title:       $UserTitle" -ForegroundColor Green
Write-Host ""

# Initialize generator
$generator = New-MockDataGenerator -Domain "dataflow.local"

# Create the protagonist user
$protagonist = @{
    Id = [guid]::NewGuid().ToString()
    FirstName = ($UserName -split ' ')[0]
    LastName = ($UserName -split ' ')[-1]
    DisplayName = $UserName
    Username = ($UserEmail -split '@')[0]
    Email = $UserEmail
    Department = $UserDepartment
    JobTitle = $UserTitle
    Phone = "+1-555-100-0001"
    Office = "HQ-401"
    Manager = $null
    Created = (Get-Date).AddYears(-2)
    LastLogin = Get-Date
    IsEnabled = $true
}

Write-Host "Generating $ColleagueCount colleagues..." -ForegroundColor Yellow
$colleagues = @{}
for ($i = 0; $i -lt $ColleagueCount; $i++) {
    $person = $generator.GeneratePerson()
    $colleagues[$person.Id] = $person
}

# Add protagonist to users
$users = @{ $protagonist.Id = $protagonist }
foreach ($c in $colleagues.Values) {
    $users[$c.Id] = $c
}

Write-Host "Generating $InboxEmailCount inbox emails (TO protagonist)..." -ForegroundColor Yellow
$emails = @{}

# Email subjects with more variety
$inboxSubjects = @(
    "Quick question about the {topic} pipeline",
    "RE: {topic} deployment status",
    "FW: Customer feedback on {topic}",
    "Need your input on {topic}",
    "Weekly {topic} status update",
    "URGENT: {topic} failure in production",
    "Can you review my {topic} PR?",
    "Meeting notes: {topic} discussion",
    "Heads up about {topic} changes",
    "Thanks for help with {topic}!",
    "{topic} - action items from standup",
    "Question about {topic} schema changes",
    "FYI: {topic} documentation updated",
    "Blocked on {topic} - need your advice",
    "Great work on {topic}!",
    "RE: RE: {topic} timeline",
    "Invitation: {topic} deep dive",
    "Reminder: {topic} deadline tomorrow",
    "{topic} performance metrics",
    "Ideas for improving {topic}"
)

$topics = @(
    "Snowflake", "Spark", "dbt", "Airflow", "Kafka", "data quality",
    "ETL", "dashboard", "metrics", "pipeline", "ingestion", "warehouse",
    "Delta Lake", "Databricks", "streaming", "batch processing", "ML model",
    "feature store", "data catalog", "lineage", "governance", "cost optimization"
)

$colleagueList = @($colleagues.Values)

for ($i = 0; $i -lt $InboxEmailCount; $i++) {
    $sender = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
    $subject = $inboxSubjects[(Get-Random -Maximum $inboxSubjects.Count)]
    $topic = $topics[(Get-Random -Maximum $topics.Count)]
    $subject = $subject -replace '\{topic\}', $topic
    
    $daysAgo = Get-Random -Minimum 0 -Maximum 60
    $receivedDate = (Get-Date).AddDays(-$daysAgo).AddHours(-(Get-Random -Maximum 12))
    
    $email = @{
        Id = [guid]::NewGuid().ToString()
        Subject = $subject
        From = $sender.Email
        FromName = $sender.DisplayName
        To = $protagonist.Email
        ToName = $protagonist.DisplayName
        Cc = ""
        Body = $generator.GenerateEmailBody($subject)
        IsRead = ($daysAgo -gt 3) -or ((Get-Random -Maximum 3) -eq 0)
        HasAttachments = (Get-Random -Maximum 6) -eq 0
        Importance = @("Normal", "Normal", "Normal", "Normal", "High", "Low")[(Get-Random -Maximum 6)]
        ReceivedDate = $receivedDate.ToString("yyyy-MM-ddTHH:mm:ss")
        FolderPath = "Inbox"
        ConversationId = [guid]::NewGuid().ToString()
    }
    $emails[$email.Id] = $email
}

Write-Host "Generating $SentEmailCount sent emails (FROM protagonist)..." -ForegroundColor Yellow

$sentSubjects = @(
    "RE: {topic} update",
    "Follow-up on {topic}",
    "{topic} - my analysis",
    "Here's the {topic} documentation",
    "RE: Need your input on {topic}",
    "Thoughts on {topic} approach",
    "{topic} PR ready for review",
    "Summary: {topic} meeting",
    "FW: {topic} requirements",
    "Quick update on {topic}"
)

for ($i = 0; $i -lt $SentEmailCount; $i++) {
    $recipient = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
    $subject = $sentSubjects[(Get-Random -Maximum $sentSubjects.Count)]
    $topic = $topics[(Get-Random -Maximum $topics.Count)]
    $subject = $subject -replace '\{topic\}', $topic
    
    $daysAgo = Get-Random -Minimum 0 -Maximum 60
    $sentDate = (Get-Date).AddDays(-$daysAgo).AddHours(-(Get-Random -Maximum 12))
    
    $email = @{
        Id = [guid]::NewGuid().ToString()
        Subject = $subject
        From = $protagonist.Email
        FromName = $protagonist.DisplayName
        To = $recipient.Email
        ToName = $recipient.DisplayName
        Cc = ""
        Body = $generator.GenerateEmailBody($subject)
        IsRead = $true
        HasAttachments = (Get-Random -Maximum 8) -eq 0
        Importance = "Normal"
        ReceivedDate = $sentDate.ToString("yyyy-MM-ddTHH:mm:ss")
        FolderPath = "Sent Items"
        ConversationId = [guid]::NewGuid().ToString()
    }
    $emails[$email.Id] = $email
}

Write-Host "Generating $MeetingCount meetings (with protagonist)..." -ForegroundColor Yellow

$meetingTypes = @(
    "1:1 with {person}",
    "Sprint Planning",
    "Sprint Retrospective", 
    "Daily Standup",
    "Architecture Review: {topic}",
    "Code Review: {topic}",
    "{topic} Deep Dive",
    "Data Quality Review",
    "Pipeline Postmortem: {topic}",
    "Tech Debt Planning",
    "Cross-team Sync",
    "Stakeholder Update",
    "{topic} Training",
    "Team All-Hands",
    "OKR Review",
    "{topic} Design Discussion",
    "Interview: Data Engineer",
    "Mentoring Session"
)

$meetings = @{}

for ($i = 0; $i -lt $MeetingCount; $i++) {
    $meetingType = $meetingTypes[(Get-Random -Maximum $meetingTypes.Count)]
    $topic = $topics[(Get-Random -Maximum $topics.Count)]
    $randomColleague = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
    
    $meetingType = $meetingType -replace '\{topic\}', $topic
    $meetingType = $meetingType -replace '\{person\}', $randomColleague.DisplayName
    
    # Mix of past and future meetings
    $daysOffset = Get-Random -Minimum -14 -Maximum 21
    $startHour = Get-Random -Minimum 8 -Maximum 17
    $duration = @(30, 30, 45, 60, 60, 90)[(Get-Random -Maximum 6)]
    
    $startTime = (Get-Date).Date.AddDays($daysOffset).AddHours($startHour)
    $endTime = $startTime.AddMinutes($duration)
    
    # Randomly decide if protagonist is organizer or attendee
    $isOrganizer = (Get-Random -Maximum 2) -eq 0
    
    # Pick 1-5 additional attendees
    $attendeeCount = Get-Random -Minimum 1 -Maximum 6
    $attendees = @($protagonist.Email)
    for ($j = 0; $j -lt $attendeeCount; $j++) {
        $attendee = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
        if ($attendees -notcontains $attendee.Email) {
            $attendees += $attendee.Email
        }
    }
    
    $organizer = if ($isOrganizer) { $protagonist.Email } else { $randomColleague.Email }
    if (-not $isOrganizer -and $attendees -notcontains $organizer) {
        $attendees += $organizer
    }
    
    $meeting = @{
        Id = [guid]::NewGuid().ToString()
        Subject = $meetingType
        Organizer = $organizer
        OrganizerName = if ($isOrganizer) { $protagonist.DisplayName } else { $randomColleague.DisplayName }
        Attendees = ($attendees | Where-Object { $_ -ne $organizer }) -join "; "
        StartTime = $startTime.ToString("yyyy-MM-ddTHH:mm:ss")
        EndTime = $endTime.ToString("yyyy-MM-ddTHH:mm:ss")
        Location = @("Zoom", "Teams", "Google Meet", "Conference Room A", "Conference Room B", "Huddle Space")[(Get-Random -Maximum 6)]
        IsRecurring = (Get-Random -Maximum 4) -eq 0
        Body = "Agenda:`n1. Review previous action items`n2. Main discussion: $topic`n3. Next steps`n4. Q&A"
        ReminderMinutes = @(5, 10, 15, 30)[(Get-Random -Maximum 4)]
        IsAccepted = $true
        IsCancelled = $false
    }
    $meetings[$meeting.Id] = $meeting
}

# Build final data structure
$data = @{
    GeneratedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    Protagonist = @{
        Id = $protagonist.Id
        Email = $protagonist.Email
        DisplayName = $protagonist.DisplayName
        Department = $protagonist.Department
        JobTitle = $protagonist.JobTitle
    }
    Users = $users
    Emails = $emails
    Meetings = $meetings
    Contacts = @{}  # Could add external contacts later
}

# Ensure output directory exists
$outputDir = Split-Path -Parent $OutputPath
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

# Write JSON
Write-Host ""
Write-Host "Writing data to: $OutputPath" -ForegroundColor Yellow
$data | ConvertTo-Json -Depth 10 | Set-Content -Path $OutputPath -Encoding UTF8

# Summary
$inboxCount = ($emails.Values | Where-Object { $_.FolderPath -eq "Inbox" }).Count
$sentCount = ($emails.Values | Where-Object { $_.FolderPath -eq "Sent Items" }).Count
$futureMeetings = ($meetings.Values | Where-Object { [datetime]$_.StartTime -gt (Get-Date) }).Count

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Data Generation Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Protagonist:     $UserName <$UserEmail>" -ForegroundColor White
Write-Host "  Colleagues:      $($colleagues.Count)" -ForegroundColor White
Write-Host "  Inbox Emails:    $inboxCount" -ForegroundColor White
Write-Host "  Sent Emails:     $sentCount" -ForegroundColor White
Write-Host "  Total Meetings:  $($meetings.Count)" -ForegroundColor White
Write-Host "  Future Meetings: $futureMeetings" -ForegroundColor White
Write-Host ""
Write-Host "  Next: Run 'python console_client.py' to test" -ForegroundColor Cyan
Write-Host ""
