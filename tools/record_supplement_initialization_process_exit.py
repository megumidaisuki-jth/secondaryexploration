"""Metadata-only explicit recovery evidence for disappeared S5 process tree."""
import json
from pathlib import Path
import subprocess
import sys
from tools.supplement_initialization_common import ROOT,OUT,sha,save,encode
from tools.run_supplement_initialization import execution_context
from tools.pipeline_supplement_initialization import validate_preflight_snapshot,DIAG
from tools.schedule_supplement_initialization_v3 import overlay_binding

INCIDENT=DIAG/'recovery-process-20261008-task-v1'

def record_task():
    command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $task=Get-ScheduledTask -TaskName 'SecondaryExploration-S5-Initialization-20261008'; [pscustomobject]@{TaskName=$task.TaskName; Actions=@($task.Actions|Select-Object Execute,Arguments,WorkingDirectory); Settings=($task.Settings|Select-Object RestartCount,ExecutionTimeLimit,MultipleInstances,DisallowStartIfOnBatteries,StopIfGoingOnBatteries); Principal=($task.Principal|Select-Object UserId,RunLevel,LogonType); TriggerCount=@($task.Triggers|Where-Object {$null -ne $_}).Count} | ConvertTo-Json -Depth 5 -WarningAction SilentlyContinue"
    shell='C:/Users/jiate/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'
    process=subprocess.run([shell,'-NoProfile','-Command',command],capture_output=True,check=True)
    definition=json.loads(process.stdout.decode('utf-8-sig'))
    assert definition['Settings']['RestartCount']==0 and definition['Settings']['ExecutionTimeLimit']=='PT0S'
    assert definition['TriggerCount']==0 and definition['Principal']['RunLevel']==0
    save(INCIDENT/'task-definition.json',definition)
    print('One-shot limited-user task definition archived; no triggers, timeout or retry.')

def main():
    assert not (INCIDENT/'incident.json').exists()
    validate_preflight_snapshot(json.loads((OUT/'snapshot-preflight.json').read_bytes()))
    context,_=execution_context(); assert json.loads((OUT/'scheduler-v3-binding.json').read_bytes())==overlay_binding()
    status=json.loads((OUT/'pipeline-status.json').read_bytes()); progress=json.loads((OUT/'progress.json').read_bytes())
    paths=[OUT/'PIPELINE.lock',OUT/'RUNNING.lock',OUT/'pipeline-status.json',OUT/'progress.json',
           Path(status['stderr']),Path(status['stdout']),
           DIAG/'20261008T091812-v3-supervisor.stderr.txt',DIAG/'20261008T091812-v3-supervisor.stdout.txt',
           *sorted((OUT/'run-progress').glob('*.tmp'))]
    rows=[]
    for p in paths:
        data=p.read_bytes(); rows.append({'path':p.relative_to(ROOT).as_posix(),'name':p.name,'bytes':len(data),'sha256':sha(data),
                                        'operation':'move' if p.name.endswith(('.lock','.tmp')) else 'copy'})
    chunks={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for uid in progress['active_units'] for p in (OUT/'runs'/uid/'chunks').glob('*.gz')}
    command="$a=[datetime]'2026-10-08 09:28:00'; $b=[datetime]'2026-10-08 09:33:00'; Get-WinEvent -FilterHashtable @{LogName='System';StartTime=$a;EndTime=$b} | Where-Object {$_.ProviderName -eq 'Microsoft-Windows-WindowsUpdateClient' -or ($_.ProviderName -eq 'Service Control Manager' -and $_.Id -eq 7045)} | Select-Object TimeCreated,Id,ProviderName,Message | ConvertTo-Json -Depth 4"
    # PowerShell redirected stdout uses the OEM/default encoding, force JSON
    # Unicode by a separate UTF-8 console encoding assignment.
    command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "+command
    powershell=Path('C:/Users/jiate/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe')
    events=subprocess.run([str(powershell),'-NoProfile','-Command',command],capture_output=True,check=True)
    save(INCIDENT/'windows-events.json',json.loads(events.stdout.decode('utf-8-sig')))
    save(INCIDENT/'incident.json',{'reason':'User authorized diagnosis and restart after process disappearance',
        'old_status':status,'old_progress':progress,'files_to_preserve':rows,'active_unit_chunk_sha256':chunks,
        'frozen_worker_context_sha256':sha(encode(context)),'overlay':overlay_binding(),
        'observation':'Last progress 09:30:06 Hong Kong. Windows logs show Codex package installation start 09:30:06 and success 09:30:09. Old PIDs absent, no Python stderr, no reboot.',
        'inference':'Application update/lifecycle likely terminated app-owned process tree; no termination exit receipt, therefore exact cause not proven.',
        'new_launch':'Windows on-demand task, same limited current user, no trigger/restart/time limit; exact existing v3 supervisor and science retained',
        'archive_checked':False})
    print('Frozen context passed; process incident and Windows update evidence recorded.')

if __name__=='__main__':
    if sys.argv[1:]==['--task-definition']: record_task()
    else:
        assert not sys.argv[1:]
        main()
