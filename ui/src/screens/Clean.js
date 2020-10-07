import React, { Component } from 'react';
import {
  Alert,
  Button,
  Col,
  Modal,
  Row,
  Table,
  Spinner,
} from 'react-bootstrap';
import { Route } from 'react-router-dom';
import axios from 'axios';
import { pick } from 'lodash';
import { HiMenu, HiSortAscending, HiSortDescending } from 'react-icons/hi';

class Clean extends Component {

  _handleSubmit = async() => {
    this.setState({ isProcessing: true });
    const formData = new FormData();
    formData.append('project_id', this.state.project_id);
    formData.append('feedback', JSON.stringify(this.state.feedbackMap));
    formData.append('is_new_feedback', (this.state.noNewFeedback === false ? 1 : 0));
    axios.post('http://167.71.155.153:5000/duo/api/clean', formData)
        .then(async(response) => {
          console.log(response.data);
          var res = JSON.parse(response.data);
          var { msg } = pick(res, ['msg'])
          if (msg === '[DONE]') {
            this.setState({ interactionDone: true});
          }
          else {
            var { sample, feedback, true_pos, false_pos } = pick(res, ['sample', 'feedback', 'true_pos', 'false_pos'])
            var data = JSON.parse(sample);
            true_pos =JSON.parse(true_pos);
            false_pos = JSON.parse(false_pos);
            feedback = JSON.parse(feedback);
            console.log(msg);

            for (var i in data) {
              for (var j in data[i]) {
                if (data[i][j] == null) data[i][j] = '';
                else if (typeof data[i][j] != 'string') data[i][j] = data[i][j].toString();
              }
            }
            console.log(data);

            var sortMethod = {};
            for (var h of this.state.header) {
              sortMethod[h] = 'NONE';
            }

            var feedbackMap = await this._buildFeedbackMap(data, feedback);
            this.setState({ 
              data,
              feedbackMap,
              isProcessing: false,
              noNewFeedback: false,
              true_pos,
              false_pos,
              sortMethod
            }, () => {
              console.log(this.state.true_pos, this.state.false_pos);
            });
          }
        })
        .catch(error => {
          console.log(error);
        });
  }

  _buildFeedbackMap = async(data, feedback) => {
    console.log(feedback);
    var feedbackMap = {};
    var rows = Object.keys(data);
    var cols = this.state.header;
    console.log(rows);
    console.log(cols);
    for (let i = 0; i < rows.length; i++) {
      var tup = {};
      for (let j = 0; j < cols.length; j++) {
        var cell = feedback.find(e => {
          var trimmedCol = cols[j].replace(/[\n\r]+/g, '');
          return e.row === parseInt(rows[i]) && e.col === trimmedCol;
        });
        tup[cols[j]] = cell.marked;
      }
      feedbackMap[rows[i]] = tup;
    }
    return feedbackMap;
  }

  _getSampleData = async(project_id) => {
    const formData = new FormData();
    formData.append('project_id', project_id);
    console.log(formData.get('project_id'));
    axios.post('http://167.71.155.153:5000/duo/api/sample', formData)
        .then(async(response) => {
          var res = JSON.parse(response.data);
          var { sample, feedback, msg, true_pos, false_pos } = pick(res, ['sample', 'feedback', 'msg', 'true_pos', 'false_pos'])
          var data = JSON.parse(sample);
          true_pos = JSON.parse(true_pos);
          false_pos = JSON.parse(false_pos);
          feedback = JSON.parse(feedback);
          console.log(msg);

          for (var i in data) {
            for (var j in data[i]) {
              if (data[i][j] == null) data[i][j] = '';
              else if (typeof data[i][j] != 'string') data[i][j] = data[i][j].toString();
              if (!isNaN(data[i][j]) && Math.ceil(parseFloat(data[i][j])) - parseFloat(data[i][j]) === 0) {
                data[i][j] = Math.ceil(data[i][j]).toString();
              }
            }
          }
          console.log(data);

          var feedbackMap = await this._buildFeedbackMap(data, feedback);
          this.setState({ data, feedbackMap, true_pos, false_pos }, () => {
            console.log(this.state.true_pos, this.state.false_pos);
          });
        })
        .catch(error => {
          console.log(error);
        });
  }

  _handleResume = async(sample, true_pos, false_pos, feedback) => {
    var data = JSON.parse(sample);
    true_pos = JSON.parse(true_pos);
    false_pos = JSON.parse(false_pos);
    feedback = JSON.parse(feedback);

    for (var i in data) {
      for (var j in data[i]) {
        if (data[i][j] == null) data[i][j] = '';
        else if (typeof data[i][j] != 'string') data[i][j] = data[i][j].toString();
        if (!isNaN(data[i][j]) && Math.ceil(parseFloat(data[i][j])) - parseFloat(data[i][j]) === 0) {
          data[i][j] = Math.ceil(data[i][j]).toString();
        }
      }
    }
    console.log(data);

    var feedbackMap = await this._buildFeedbackMap(data, feedback);
    this.setState({ data, feedbackMap, true_pos, false_pos }, () => {
      console.log(this.state.true_pos, this.state.false_pos);
    });
  }

  _renderHeader = async() => {
    console.log('building header');
    return this.state.header.map((item, idx) => <th key={'header_'.concat(idx)}>{item}</th>);
  }


  _handleCellClick = async(key, event) => {
    var pieces = key.split('_');
    var idx = parseInt(pieces.shift());
    var attr = pieces.join('_');
    var feedbackMap = this.state.feedbackMap;
    feedbackMap[idx][attr] = !feedbackMap[idx][attr]
    this.setState({ feedbackMap });
  }

  _handleRefreshClick = async() => {
    var noNewFeedback = true;
    this.setState({ noNewFeedback }, async () => {
      await this._handleSubmit();
    });
  }

  _handleDone = async() => {
    this.setState({ isProcessing: true, interactionDone: true });
  }

  _handleReturnHome = async(history) => {
    history.push('/duo/');
  }

  _handleSort = async(attr, event) => {
    var sortMethod = this.state.sortMethod;
    var data = this.state.data;
    switch (sortMethod[attr]) {
      case 'NONE':
        for (var h of this.state.header) {
          if (h === attr) {
            sortMethod[attr] = 'ASC';
          } else sortMethod[attr] = 'NONE';
        }
        // ascending sort
        data.sort((a, b) => {
          return a[attr] > b[attr] ? 1 : -1;
        });
        break;
      case 'DESC':
        for (var h of this.state.header) {
          if (h === attr) {
            sortMethod[attr] = 'ASC';
          } else sortMethod[attr] = 'NONE';
        }
        // ascending sort
        data.sort((a, b) => {
          return a[attr] > b[attr] ? 1 : -1;
        });
        break;
      case 'ASC':
        for (var h of this.state.header) {
          if (h === attr) {
            sortMethod[attr] = 'DESC';
          } else sortMethod[attr] = 'NONE';
        }
        // descending sort
        data.sort((a, b) => {
          return a[attr] < b[attr] ? 1 : -1;
        });
        break;
      default:
        break;
    }
    this.setState({ sortMethod, data })
  }

  componentDidMount() {
    const { header, project_id, scenario_id, scenario_desc, is_resuming, sample, true_pos, false_pos, feedback } = this.props.location;
    var sortMethod = {};
    for (var h of header) {
      sortMethod[h] = 'NONE';
    }
    this.setState({ header, project_id, scenario_id, scenario_desc, sortMethod }, async() => {
      if (is_resuming === false) {
        await this._getSampleData(this.state.project_id);
        console.log('got sample');
      } else {
        await this._handleResume(sample, true_pos, false_pos, feedback);
        console.log('resumed');
      }
      console.log(this.state);
    });
  }

  constructor(props) {
    super(props);

    this.state = {
      data: [],
      feedbackMap: {},
      header: [],
      project_id: 0,
      scenario_id: 0,
      isProcessing: false,
      noNewFeedback: false,
      true_pos: 0,
      false_pos: 0,
      interactionDone: false,
      scenario_desc: null,
      sortMethod: {}
    };
  }

  render() {
    return (
      <Route render={({ history }) => (
        <div className='site-page'>
          <Modal show={this.state.isProcessing} animation={false} backdrop='static'>
            <Modal.Body>{
              this.state.interactionDone && (
                <div className='content-centered'>
                  <span>Thank you for participating! Please see your handout for next steps!</span>
                  <br />
                  <div className='results-header box-blur'>
                    <p><strong>Your Scores</strong></p>
                    <Table responsive>
                      <thead>
                        <tr>
                          <th><p><strong>True Positives</strong></p></th>
                          <th><p><strong>False Positives</strong></p></th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>{this.state.true_pos}</td>
                          <td>{this.state.false_pos}</td>
                        </tr>
                      </tbody>
                    </Table>
                  </div>
                  <br />
                  <Button
                    variant='success'
                    className='btn-round box-blur'
                    size='lg'
                    onClick={() => this._handleReturnHome(history)}>
                    RETURN HOME
                  </Button>
                </div>
              )}
              { this.state.interactionDone === false && (
                <div>
                  <p><strong>'Processing...'</strong></p>
                  <Spinner animation='border' />  
                </div>
              )}
            </Modal.Body>
          </Modal>
          <Row className='content-centered'>
            <Col md={4}>
              <p style={{float: 'left'}}><a style={{display: 'table-cell'}} href="https://github.com/blazerzero/duo-help/blob/master/README.md" target='_blank' rel='noopener noreferrer'>Need help or a guide? Click here!</a></p>
            </Col>
            <Col>
              <div className='results-header box-blur'>
                <span className='results-title'>Duo</span>
                <p><strong>Scenario Description: </strong>{this.state.scenario_desc}</p>
                <p><strong>Project ID: </strong>{this.state.project_id}</p>
              </div>
            </Col>
          </Row>
          <Row className='content-centered'>
            <Col md={7}>
              <Alert variant='warning' style={{border: '1px black solid'}}>Yellow cells indicate cells you marked as noisy.</Alert>
            </Col>
          </Row>
          {Object.keys(this.state.data).length > 0 && (
            <div>
              <Row className='content-centered'>
                <Col>
                  <Row>
                    <Table bordered responsive>
                      <thead>
                        <tr>
                          { this.state.header.map((item) => {
                            return (
                              <th key={'header_'.concat(item)}>
                                {item}
                                {this.state.sortMethod[item] === 'ASC'
                                  ? <HiSortAscending onClick={this._handleSort.bind(this, item)} />
                                  : (this.state.sortMethod[item] == 'DESC' ? <HiSortDescending onClick={this._handleSort.bind(this, item)} /> : <HiMenu onClick={this._handleSort.bind(this, item)} />)
                                }
                              </th>)
                          }) }
                        </tr>
                      </thead>
                      <tbody>
                      { Object.keys(this.state.data).map((i) => {
                        return (
                          <tr key={i}>
                            { Object.keys(this.state.data[i]).map((j) => {
                              var key = i.toString().concat('_', j);
                              return <td
                                  key={key}
                                  style={{cursor: 'pointer', backgroundColor: (!!this.state.feedbackMap[i][j] ? '#FFF3CD' : 'white')}}
                                  onClick={this._handleCellClick.bind(this, key)}>
                                  {this.state.data[i][j]}
                              </td>
                            }) }
                          </tr>
                        )
                      }) }
                      </tbody>
                    </Table>
                  </Row>
                  <Row>
                    <Col md={4}>
                      <Button
                          variant='primary'
                          className='btn-round right box-blur'
                          size='lg'
                          onClick={this._handleRefreshClick}>
                        REFRESH SAMPLE
                      </Button>
                    </Col>
                    <Col md={{ span: 4, offset: 4 }}>
                      <Row>
                        <Button
                            variant='success'
                            className='btn-round right box-blur'
                            size='lg'
                            onClick={this._handleSubmit}>
                          SUBMIT FEEDBACK
                        </Button>
                        <Button
                            variant='secondary'
                            className='btn-round right box-blur'
                            size='lg'
                            onClick={this._handleDone}>
                          I'M ALL DONE
                        </Button>
                      </Row>
                    </Col>
                  </Row>
                </Col>
              </Row>
            </div>
          )}
        </div>
      )} />
    );
  }
}

export default Clean;
