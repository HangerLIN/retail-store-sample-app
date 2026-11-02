import jenkins.model.Jenkins
import hudson.model.*
import hudson.security.*
import hudson.slaves.*
import hudson.plugins.git.*
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import hudson.triggers.SCMTrigger

def j = Jenkins.get()
j.setNumExecutors(0)
def realm = new HudsonPrivateSecurityRealm(false)
realm.createAccount('learner', new File('/run/retail/admin-password').text.trim())
j.setSecurityRealm(realm)
def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
strategy.setAllowAnonymousRead(false)
j.setAuthorizationStrategy(strategy)
j.setSlaveAgentPort(-1)
def node = j.getNode('mac-agent')
if (node == null) {
  node = new DumbSlave('mac-agent', '/Users/lth/Documents/ChatGPT/k/retail-store-sample-app/env/agent-work', new JNLPLauncher(true))
  node.setNumExecutors(1)
  node.setLabelString('retail-mac')
  j.addNode(node)
}
new File('/run/retail/agent-secret').text = node.toComputer().getJnlpMac()
if (j.getItem('retail-local') == null) {
  def job = j.createProject(WorkflowJob, 'retail-local')
  def scm = new GitSCM([new UserRemoteConfig('https://github.com/HangerLIN/retail-store-sample-app.git',null,null,null)], [new BranchSpec('*/main')], false, [], null, null, [])
  job.setDefinition(new CpsScmFlowDefinition(scm, 'Jenkinsfile'))
  job.addProperty(new ParametersDefinitionProperty(new ChoiceParameterDefinition('ACTION', ['deploy','reconcile'] as String[], 'Publish or restore last verified release')))
  job.addTrigger(new SCMTrigger('H/2 * * * *'))
  job.save()
}
j.save()
