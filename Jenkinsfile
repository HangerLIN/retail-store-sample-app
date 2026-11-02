pipeline {
  agent { label 'retail-mac' }
  options { disableConcurrentBuilds(); timestamps(); timeout(time: 90, unit: 'MINUTES'); buildDiscarder(logRotator(numToKeepStr: '10')) }
  parameters { choice(name: 'ACTION', choices: ['deploy', 'reconcile'], description: '发布，或仅恢复最后验证成功的版本') }
  triggers { pollSCM('H/2 * * * *') }
  stages {
    stage('Preflight and reconcile') {
      steps {
        sh '''
          rm -rf reports
          mkdir -p reports
          rm -rf src/cart/target/surefire-reports src/orders/target/surefire-reports src/ui/target/surefire-reports
        '''
        sh 'bash learning/scripts/ci.sh preflight'
        script { sh "bash learning/scripts/ci.sh ${params.ACTION == 'reconcile' ? 'reconcile' : 'prepare'}" }
        script { env.PUBLISH = params.ACTION == 'deploy' ? sh(script: 'bash learning/scripts/ci.sh needed', returnStdout: true).trim() : 'no' }
      }
    }
    stage('Test and build') {
      when { expression { env.PUBLISH == 'yes' } }
      steps { sh 'bash learning/scripts/ci.sh build' }
    }
    stage('Deploy, verify and record') {
      when { expression { env.PUBLISH == 'yes' } }
      steps { sh 'bash learning/scripts/ci.sh publish' }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'reports/*.json,reports/*.jsonl,reports/*.log', allowEmptyArchive: true
      junit testResults: 'src/*/target/surefire-reports/TEST-*.xml', allowEmptyResults: true
    }
  }
}
