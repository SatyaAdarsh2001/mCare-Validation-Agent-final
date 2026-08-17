import { NgModule }            from '@angular/core';
import { BrowserModule }       from '@angular/platform-browser';
import { HttpClientModule }    from '@angular/common/http';
import { FormsModule }         from '@angular/forms';

import { AppComponent }        from './app.component';
import { ValidationModalComponent }
  from './components/validation-modal/validation-modal.component';

@NgModule({
  declarations: [
    AppComponent,
    ValidationModalComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }