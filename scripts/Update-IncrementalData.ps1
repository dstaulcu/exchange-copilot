<#
.SYNOPSIS
    Generates incremental Exchange data - new emails and meetings as time passes.
    
.DESCRIPTION
    Simulates time passing by:
    - Adding new inbox emails (recent messages)
    - Adding new sent emails
    - Scheduling new meetings
    - Optionally marking old emails as read
    
.PARAMETER DataPath
    Path to the existing exchange_mcp.json data file.
    
.PARAMETER NewInboxCount
    Number of new inbox emails to add.
    
.PARAMETER NewSentCount
    Number of new sent emails to add.
    
.PARAMETER NewMeetingCount
    Number of new meetings to add.
    
.PARAMETER MarkReadPercent
    Percentage of previously unread emails to mark as read (0-100).
#>

param(
    [string]$DataPath = ".\data\exchange_mcp.json",
    [int]$NewInboxCount = 20,
    [int]$NewSentCount = 10,
    [int]$NewMeetingCount = 8,
    [int]$MarkReadPercent = 50,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

# Source the mock data generator
. "$PSScriptRoot\..\src\utils\MockDataGenerator.ps1"

if (-not $Quiet) {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Incremental Data Update" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

# Load existing data
if (-not (Test-Path $DataPath)) {
    Write-Error "Data file not found: $DataPath. Run Generate-SingleUserData.ps1 first."
    exit 1
}

$data = Get-Content $DataPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable

$protagonist = $data.Protagonist
$users = $data.Users
$emails = $data.Emails
$meetings = $data.Meetings

if (-not $Quiet) {
    Write-Host ""
    Write-Host "Current data:" -ForegroundColor Yellow
    Write-Host "  User: $($protagonist.DisplayName) <$($protagonist.Email)>"
    Write-Host "  Emails: $($emails.Count) | Meetings: $($meetings.Count)"
    Write-Host ""
}

# Initialize generator
$generator = New-MockDataGenerator -Domain "dataflow.local"

# Get colleague list (everyone except protagonist)
$colleagueList = @($users.Values | Where-Object { $_.Email -ne $protagonist.Email })

# Email subjects for new messages
$newSubjects = @(
    "Quick update on {topic}",
    "RE: {topic} follow-up",
    "New requirement for {topic}",
    "{topic} status check",
    "Urgent: {topic} issue",
    "Completed: {topic} task",
    "Question about {topic}",
    "Review needed: {topic}",
    "FW: Important {topic} info",
    "Thanks for the {topic} help"
)

$topics = @(
    "Snowflake", "Spark", "dbt", "Airflow", "Kafka", "data quality",
    "ETL", "dashboard", "metrics", "pipeline", "ingestion", "warehouse",
    "Delta Lake", "Databricks", "streaming", "ML model", "feature store"
)

# Track new items
$newEmailIds = @()
$newMeetingIds = @()

# Generate new inbox emails
if (-not $Quiet) {
    Write-Host "Adding $NewInboxCount new inbox emails..." -ForegroundColor Yellow
}

for ($i = 0; $i -lt $NewInboxCount; $i++) {
    $sender = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
    $subject = $newSubjects[(Get-Random -Maximum $newSubjects.Count)]
    $topic = $topics[(Get-Random -Maximum $topics.Count)]
    $subject = $subject -replace '\{topic\}', $topic
    
    # Recent emails (last 2 days)
    $hoursAgo = Get-Random -Minimum 0 -Maximum 48
    $receivedDate = (Get-Date).AddHours(-$hoursAgo)
    
    $emailId = [guid]::NewGuid().ToString()
    $email = @{
        Id = $emailId
        Subject = $subject
        From = $sender.Email
        FromName = $sender.DisplayName
        To = $protagonist.Email
        ToName = $protagonist.DisplayName
        Cc = ""
        Body = $generator.GenerateEmailBody($subject)
        IsRead = $false  # New emails are unread
        HasAttachments = (Get-Random -Maximum 8) -eq 0
        Importance = @("Normal", "Normal", "Normal", "Normal", "High")[(Get-Random -Maximum 5)]
        ReceivedDate = $receivedDate.ToString("yyyy-MM-ddTHH:mm:ss")
        FolderPath = "Inbox"
        ConversationId = [guid]::NewGuid().ToString()
    }
    $emails[$emailId] = $email
    $newEmailIds += $emailId
}

# Generate new sent emails
if (-not $Quiet) {
    Write-Host "Adding $NewSentCount new sent emails..." -ForegroundColor Yellow
}

$sentSubjects = @(
    "RE: {topic}",
    "Follow-up: {topic}",
    "{topic} update",
    "Here's the {topic} info",
    "Completed: {topic}"
)

for ($i = 0; $i -lt $NewSentCount; $i++) {
    $recipient = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
    $subject = $sentSubjects[(Get-Random -Maximum $sentSubjects.Count)]
    $topic = $topics[(Get-Random -Maximum $topics.Count)]
    $subject = $subject -replace '\{topic\}', $topic
    
    $hoursAgo = Get-Random -Minimum 0 -Maximum 48
    $sentDate = (Get-Date).AddHours(-$hoursAgo)
    
    $emailId = [guid]::NewGuid().ToString()
    $email = @{
        Id = $emailId
        Subject = $subject
        From = $protagonist.Email
        FromName = $protagonist.DisplayName
        To = $recipient.Email
        ToName = $recipient.DisplayName
        Cc = ""
        Body = $generator.GenerateEmailBody($subject)
        IsRead = $true
        HasAttachments = (Get-Random -Maximum 10) -eq 0
        Importance = "Normal"
        ReceivedDate = $sentDate.ToString("yyyy-MM-ddTHH:mm:ss")
        FolderPath = "Sent Items"
        ConversationId = [guid]::NewGuid().ToString()
    }
    $emails[$emailId] = $email
    $newEmailIds += $emailId
}

# Generate new meetings
if (-not $Quiet) {
    Write-Host "Adding $NewMeetingCount new meetings..." -ForegroundColor Yellow
}

$meetingTypes = @(
    "1:1 with {person}",
    "Quick sync: {topic}",
    "{topic} Review",
    "Ad-hoc: {topic} Discussion",
    "Follow-up: {topic}",
    "{topic} Planning"
)

for ($i = 0; $i -lt $NewMeetingCount; $i++) {
    $meetingType = $meetingTypes[(Get-Random -Maximum $meetingTypes.Count)]
    $topic = $topics[(Get-Random -Maximum $topics.Count)]
    $randomColleague = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
    
    $meetingType = $meetingType -replace '\{topic\}', $topic
    $meetingType = $meetingType -replace '\{person\}', $randomColleague.DisplayName
    
    # Future meetings (next 1-14 days)
    $daysAhead = Get-Random -Minimum 1 -Maximum 15
    $startHour = Get-Random -Minimum 8 -Maximum 17
    $duration = @(30, 30, 45, 60)[(Get-Random -Maximum 4)]
    
    $startTime = (Get-Date).Date.AddDays($daysAhead).AddHours($startHour)
    $endTime = $startTime.AddMinutes($duration)
    
    $isOrganizer = (Get-Random -Maximum 2) -eq 0
    
    $attendees = @($protagonist.Email)
    $attendeeCount = Get-Random -Minimum 1 -Maximum 4
    for ($j = 0; $j -lt $attendeeCount; $j++) {
        $attendee = $colleagueList[(Get-Random -Maximum $colleagueList.Count)]
        if ($attendees -notcontains $attendee.Email) {
            $attendees += $attendee.Email
        }
    }
    
    $organizer = if ($isOrganizer) { $protagonist.Email } else { $randomColleague.Email }
    
    $meetingId = [guid]::NewGuid().ToString()
    $meeting = @{
        Id = $meetingId
        Subject = $meetingType
        Organizer = $organizer
        OrganizerName = if ($isOrganizer) { $protagonist.DisplayName } else { $randomColleague.DisplayName }
        Attendees = ($attendees | Where-Object { $_ -ne $organizer }) -join "; "
        StartTime = $startTime.ToString("yyyy-MM-ddTHH:mm:ss")
        EndTime = $endTime.ToString("yyyy-MM-ddTHH:mm:ss")
        Location = @("Zoom", "Teams", "Google Meet", "Conference Room A")[(Get-Random -Maximum 4)]
        IsRecurring = $false
        Body = "Agenda:`n1. Discussion: $topic`n2. Action items`n3. Next steps"
        ReminderMinutes = 15
        IsAccepted = $true
        IsCancelled = $false
    }
    $meetings[$meetingId] = $meeting
    $newMeetingIds += $meetingId
}

# Mark some old unread emails as read
if ($MarkReadPercent -gt 0) {
    $unreadEmails = @($emails.Values | Where-Object { 
        $_.FolderPath -eq "Inbox" -and 
        -not $_.IsRead -and 
        $newEmailIds -notcontains $_.Id 
    })
    
    $toMarkRead = [math]::Floor($unreadEmails.Count * $MarkReadPercent / 100)
    
    if ($toMarkRead -gt 0 -and -not $Quiet) {
        Write-Host "Marking $toMarkRead emails as read..." -ForegroundColor Yellow
    }
    
    $shuffled = $unreadEmails | Get-Random -Count ([math]::Min($toMarkRead, $unreadEmails.Count))
    foreach ($email in $shuffled) {
        $emails[$email.Id].IsRead = $true
    }
}

# Update metadata
$data.GeneratedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
$data.LastUpdate = @{
    Timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    NewEmails = $newEmailIds
    NewMeetings = $newMeetingIds
}
$data.Emails = $emails
$data.Meetings = $meetings

# Write updated JSON
$data | ConvertTo-Json -Depth 10 | Set-Content -Path $DataPath -Encoding UTF8

# Summary
$inboxCount = ($emails.Values | Where-Object { $_.FolderPath -eq "Inbox" }).Count
$sentCount = ($emails.Values | Where-Object { $_.FolderPath -eq "Sent Items" }).Count
$unreadCount = ($emails.Values | Where-Object { $_.FolderPath -eq "Inbox" -and -not $_.IsRead }).Count

if (-not $Quiet) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  Update Complete!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  New emails added:    $($newEmailIds.Count)" -ForegroundColor White
    Write-Host "  New meetings added:  $($newMeetingIds.Count)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Total inbox:         $inboxCount ($unreadCount unread)" -ForegroundColor White
    Write-Host "  Total sent:          $sentCount" -ForegroundColor White
    Write-Host "  Total meetings:      $($meetings.Count)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Run 'python -c `"from exchange_mcp_server.server import *; sync_data()`"' to update vectors" -ForegroundColor Cyan
    Write-Host ""
}

# Output new IDs for programmatic use
@{
    NewEmailIds = $newEmailIds
    NewMeetingIds = $newMeetingIds
}
