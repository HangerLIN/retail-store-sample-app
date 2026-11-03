pipeline {
  agent { label 'retail-mac' }
  options { disableConcurrentBuilds(); timestamps(); timeout(time: 90, unit: 'MINUTES'); buildDiscarder(logRotator(numToKeepStr: '10')) }
  parameters { choice(name: 'ACTION', choices: ['deploy', 'reconcile'], description: '发布，或仅恢复最后验证成功的版本') }
  triggers { pollSCM('H/2 * * * *') }
  stages {
    stage('Preflight and reconcile') {
      steps {
        script { currentBuild.description = params.ACTION == 'reconcile' ? 'reconcile: running' : 'deploy: checking' }
        sh '''
          rm -rf reports
          mkdir -p reports
          rm -rf src/cart/target/surefire-reports src/orders/target/surefire-reports src/ui/target/surefire-reports
        '''
        sh 'bash learning/scripts/ci.sh preflight'
        script { sh "bash learning/scripts/ci.sh ${params.ACTION == 'reconcile' ? 'reconcile' : 'prepare'}" }
        script {
          env.PUBLISH = params.ACTION != 'reconcile' ? sh(script: 'bash learning/scripts/ci.sh needed', returnStdout: true).trim() : 'no'
          if (params.ACTION == 'reconcile') {
            currentBuild.description = 'reconcile: completed'
          } else if (env.PUBLISH != 'yes') {
            currentBuild.description = 'skipped: docs-only or no changes since lastGood'
            currentBuild.result = 'NOT_BUILT'
          } else {
            currentBuild.description = "deploying ${env.GIT_COMMIT.take(12)}"
          }
        }
      }
    }
    stage('Test and build') {
      when { expression { env.PUBLISH == 'yes' } }
      steps { sh 'bash learning/scripts/ci.sh build' }
    }
    stage('Deploy, verify and record') {
      when { expression { env.PUBLISH == 'yes' } }
      steps {
        sh 'bash learning/scripts/ci.sh publish'
        script { currentBuild.description = "deployed ${env.GIT_COMMIT.take(12)}" }
      }
    }
  }
  post {
    failure { script { currentBuild.description = "failed: ${currentBuild.description ?: 'initialization'}" } }
    always {
      archiveArtifacts artifacts: 'reports/*.json,reports/*.jsonl,reports/*.log', allowEmptyArchive: true
      junit testResults: 'src/*/target/surefire-reports/TEST-*.xml', allowEmptyResults: true
    }
  }
}
